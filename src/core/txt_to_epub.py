#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TXT转EPUB工具 - 将多个TXT文本文件合并为EPUB电子书

这个脚本可以将文件夹中的多个TXT文件按照特定命名规则合并为一个EPUB电子书，
便于在电子阅读器上阅读。
"""

import os
import re
import argparse
import logging
import uuid
import zipfile
import shutil
import tempfile
from pathlib import Path
from ebooklib import epub


# 配置日志系统
def setup_logger(log_level=logging.INFO):
    """配置日志系统"""
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)


# 创建全局日志对象
logger = setup_logger()


def parse_filename(filename):
    """
    从文件名中解析出小说名称、序号和章节名称
    
    Args:
        filename: 文件名字符串
        
    Returns:
        tuple: (小说名称, 章节序号, 章节标题)，解析失败则返回(None, None, None)
    """
    patterns = [
        # 标准格式：小说名称_[序号]_章节名称.txt
        r"(.+?)_\[(\d+)\]_(.+?)\.txt$",
        # 多章节合并文件: 小说名_[开始-结束].txt
        r"(.+?)_\[(\d+)-(\d+)\]\.txt$",
        # 更宽松的格式：小说名称_序号_章节名称.txt（没有方括号）
        r"(.+?)_(\d+)_(.+?)\.txt$"
    ]
    
    for i, pattern in enumerate(patterns):
        match = re.match(pattern, filename)
        if match:
            novel_name = match.group(1)
            if i == 1:  # 多章节合并文件
                chapter_number = int(match.group(2))
                chapter_title = f"第{chapter_number}章"
            else:
                chapter_number = int(match.group(2))
                chapter_title = match.group(3)
                
                # 如果章节标题是"目录"，标记为特殊序号
                if chapter_title == "目录":
                    logger.info(f"检测到目录文件: {filename}")
                    chapter_number = -1  # 使用负数使目录排在最前面，但不作为正式章节
            
            return novel_name, chapter_number, chapter_title
    
    logger.warning(f"无法解析文件名: {filename}，不符合命名规则")
    return None, None, None


def read_txt_content(file_path):
    """读取txt文件内容，自动处理编码问题"""
    file_path = Path(file_path)
    
    if not file_path.exists():
        logger.error(f"文件不存在: {file_path}")
        return "（文件不存在）"
    
    if file_path.stat().st_size == 0:
        logger.warning(f"警告：文件 {file_path} 为空文件")
        return "（空文件）"
    
    # 优先尝试最常用的编码
    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin-1']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
                if content:
                    return content
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.warning(f"读取文件 {file_path.name} 时发生错误: {e}")
    
    # 所有编码都失败时，尝试二进制读取
    try:
        with open(file_path, 'rb') as f:
            binary_data = f.read()
            # 尝试使用latin-1强制解码
            return binary_data.decode('latin-1', errors='replace')
    except Exception as e:
        logger.error(f"二进制读取文件 {file_path} 失败: {e}")
    
    return "（内容读取失败）"


def detect_novel_name(txt_files, folder_path):
    """从文件名中检测小说名称"""
    name_counter = {}
    
    for filename in txt_files:
        name, _, _ = parse_filename(filename)
        if name:
            name_counter[name] = name_counter.get(name, 0) + 1
    
    # 返回出现次数最多的小说名称
    if name_counter:
        most_common_name = max(name_counter.items(), key=lambda x: x[1])[0]
        logger.info(f"检测到小说名称: {most_common_name}")
        return most_common_name
    
    # 如果无法从文件名检测，则使用文件夹名称
    folder_name = Path(folder_path).name
    logger.info(f"无法从文件名检测小说名称，使用文件夹名称: {folder_name}")
    return folder_name


def extract_chapters(txt_files, folder_path, novel_name=None):
    """从文件列表中提取章节信息"""
    chapters = []
    detected_novel_name = None
    
    for filename in txt_files:
        name, number, title = parse_filename(filename)
        if name and number is not None and title:
            # 跳过目录文件（序号为负数的文件，如-1）
            if number < 0:
                logger.info(f"跳过目录文件: {filename}")
                continue
                
            if detected_novel_name is None:
                detected_novel_name = name
            
            chapters.append({
                'filename': filename,
                'number': number,
                'title': title,
                'path': Path(folder_path) / filename
            })
    
    # 使用指定的小说名称或检测到的小说名称
    final_novel_name = novel_name or detected_novel_name or detect_novel_name(txt_files, folder_path)
    
    # 按章节编号排序
    chapters.sort(key=lambda x: x['number'])
    
    logger.info(f"从 {len(txt_files)} 个文件中提取了 {len(chapters)} 个有效章节")
    
    return final_novel_name, chapters


def escape_html(text):
    """转义HTML特殊字符"""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def write_epub(book, output_path):
    """将EPUB书籍写入文件（优先使用 ebooklib 原生写出）

    说明：历史实现使用系统临时目录手写 OPF/NCX/container.xml 并 zip 打包。
    在部分运行环境中系统临时目录不可写，会导致必然失败；同时手写 XML 风险更高。
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 先走 ebooklib 标准写出路径
    try:
        try:
            import ebooklib
            empty_docs = []
            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                body = item.get_body_content()
                if isinstance(body, (bytes, bytearray)):
                    body_text = body.decode("utf-8", errors="ignore")
                else:
                    body_text = str(body) if body is not None else ""
                if not body_text.strip():
                    empty_docs.append(f"{getattr(item, 'file_name', '?')} ({type(item).__name__})")
            if empty_docs:
                logger.error(f"EPUB文档存在空body（ebooklib可能会失败）: {', '.join(empty_docs)}")
        except Exception:
            pass

        epub.write_epub(str(output_path), book, {})
        if output_path.exists() and output_path.stat().st_size > 1000:
            logger.info(f"EPUB文件已生成: {output_path}, 大小: {output_path.stat().st_size/1024:.2f} KB")
            return True
        logger.error(f"生成的EPUB文件失败或文件过小: {output_path}")
        return False
    except Exception as e:
        import traceback
        logger.error(f"ebooklib 写出EPUB失败，将尝试 legacy 路径: {e}")
        logger.error(f"详细错误: {traceback.format_exc()}")

    return _write_epub_legacy(book, output_path)


def _write_epub_legacy(book, output_path: Path):
    """legacy 写出路径：保留旧逻辑以便回滚（临时目录改到项目 tmp/ 下避免权限问题）"""
    try:
        project_root = Path(__file__).resolve().parents[2]
        tmp_root = project_root / "tmp"
        tmp_root.mkdir(parents=True, exist_ok=True)

        # 注意：本运行环境下 tempfile.mkdtemp() 创建的目录不可写；改用显式 mkdir
        temp_dir = tmp_root / f"epub-legacy-{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=False)
        logger.info(f"创建临时目录(legacy): {temp_dir}")
        
        # 创建mimetype文件（必须是第一个文件，且不压缩）
        mimetype_path = temp_dir / "mimetype"
        with open(mimetype_path, "w", encoding="utf-8") as f:
            f.write("application/epub+zip")
        
        # 创建META-INF目录
        meta_inf_dir = temp_dir / "META-INF"
        meta_inf_dir.mkdir(exist_ok=True)
        
        # 创建container.xml
        container_path = meta_inf_dir / "container.xml"
        with open(container_path, "w", encoding="utf-8") as f:
            f.write('''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>''')
        
        # 创建OEBPS目录（存放内容）
        oebps_dir = temp_dir / "OEBPS"
        oebps_dir.mkdir(exist_ok=True)
        
        # 写入CSS文件
        for item in book.items:
            if isinstance(item, epub.EpubItem) and item.file_name.endswith('.css'):
                css_path = oebps_dir / item.file_name
                data = item.content
                if isinstance(data, str):
                    data = data.encode("utf-8")
                with open(css_path, "wb") as f:
                    f.write(data)
        
        # 写入所有HTML文件
        for item in book.items:
            if isinstance(item, epub.EpubHtml):
                html_path = oebps_dir / item.file_name
                with open(html_path, "wb") as f:
                    # 验证内容是否为空
                    if not item.content or len(item.content) < 10:
                        safe_title = escape_html(item.title)
                        item.content = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <title>{safe_title}</title>
    <link rel="stylesheet" type="text/css" href="style.css" />
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
</head>
<body>
    <h1>{safe_title}</h1>
    <p>（本章内容已丢失，请检查原始文件）</p>
</body>
</html>'''
                    data = item.content
                    if isinstance(data, str):
                        data = data.encode("utf-8")
                    f.write(data)
        
        # 写入导航文件
        for item in book.items:
            if isinstance(item, epub.EpubNav):
                nav_path = oebps_dir / item.file_name
                data = item.content
                if isinstance(data, str):
                    data = data.encode("utf-8")
                with open(nav_path, "wb") as f:
                    f.write(data)
        
        # 写入NCX文件
        ncx_path = oebps_dir / "toc.ncx"
        ncx_content = f'''<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="unique-identifier"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle>
    <text>{book.title}</text>
  </docTitle>
  <navMap>'''
        
        # 添加各章节导航点
        for i, toc_item in enumerate(book.toc):
            if hasattr(toc_item, 'href'):
                ncx_content += f'''
    <navPoint id="navpoint-{i+1}" playOrder="{i+1}">
      <navLabel>
        <text>{toc_item.title}</text>
      </navLabel>
      <content src="{toc_item.href}"/>
    </navPoint>'''
            
        ncx_content += '''
  </navMap>
</ncx>'''
        
        with open(ncx_path, "w", encoding="utf-8") as f:
            f.write(ncx_content)
        
        # 创建OPF文件
        opf_path = oebps_dir / "content.opf"
        opf_content = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="BookId">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>{book.title}</dc:title>'''
        
        # 添加作者
        if hasattr(book, 'metadata') and 'creator' in book.metadata:
            for creator in book.metadata['creator']:
                opf_content += f'''
    <dc:creator>{creator[0]}</dc:creator>'''
        
        # 添加语言
        opf_content += f'''
    <dc:language>{book.language}</dc:language>'''
        
        # 添加唯一标识符
        unique_id = str(uuid.uuid4())
        opf_content += f'''
    <dc:identifier id="BookId">urn:uuid:{unique_id}</dc:identifier>'''
        
        # 添加其他元数据
        if hasattr(book, 'metadata'):
            if 'description' in book.metadata:
                opf_content += f'''
    <dc:description>{book.metadata['description'][0][0]}</dc:description>'''
            if 'publisher' in book.metadata:
                opf_content += f'''
    <dc:publisher>{book.metadata['publisher'][0][0]}</dc:publisher>'''
            if 'rights' in book.metadata:
                opf_content += f'''
    <dc:rights>{book.metadata['rights'][0][0]}</dc:rights>'''
        
        opf_content += '''
  </metadata>
  <manifest>'''
        
        # 添加NCX
        opf_content += '''
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'''
        
        # 添加样式表
        for i, item in enumerate([i for i in book.items if isinstance(i, epub.EpubItem) and i.file_name.endswith('.css')]):
            opf_content += f'''
    <item id="style_{i+1}" href="{item.file_name}" media-type="text/css"/>'''
        
        # 添加HTML文件
        html_items = [item for item in book.items if isinstance(item, epub.EpubHtml)]
        for item in html_items:
            item_id_str = item.id if hasattr(item, 'id') and item.id else f"item_{html_items.index(item)+1}"
            opf_content += f'''
    <item id="{item_id_str}" href="{item.file_name}" media-type="application/xhtml+xml"/>'''
        
        # 添加导航文件
        for item in [item for item in book.items if isinstance(item, epub.EpubNav)]:
            opf_content += f'''
    <item id="nav" href="{item.file_name}" media-type="application/xhtml+xml" properties="nav"/>'''
        
        opf_content += '''
  </manifest>
  <spine toc="ncx">'''
        
        # 添加所有项目到spine
        for item in book.spine:
            if item == 'nav':
                opf_content += '''
    <itemref idref="nav"/>'''
            elif isinstance(item, epub.EpubHtml):
                item_id_str = item.id if hasattr(item, 'id') and item.id else f"item_{html_items.index(item)+1}"
                opf_content += f'''
    <itemref idref="{item_id_str}"/>'''
        
        opf_content += '''
  </spine>
  <guide>'''
        
        # 添加封面和目录到指南
        for item in book.items:
            if isinstance(item, epub.EpubHtml):
                if 'cover' in item.file_name:
                    opf_content += f'''
    <reference type="cover" title="Cover" href="{item.file_name}"/>'''
                elif 'toc' in item.file_name:
                    opf_content += f'''
    <reference type="toc" title="Table of Contents" href="{item.file_name}"/>'''
        
        opf_content += '''
  </guide>
</package>'''
        
        with open(opf_path, "w", encoding="utf-8") as f:
            f.write(opf_content)
        
        # 创建EPUB文件（ZIP格式）
        if output_path.exists():
            output_path.unlink()
        
        logger.info(f"创建EPUB文件: {output_path}")
        
        with zipfile.ZipFile(output_path, 'w') as epub_file:
            # 首先添加mimetype文件，不压缩
            epub_file.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)

            # 添加其他所有文件，使用压缩
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file != "mimetype":
                        file_path = Path(root) / file
                        arcname = str(file_path.relative_to(temp_dir))
                        epub_file.write(file_path, arcname, compress_type=zipfile.ZIP_DEFLATED)

        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        # 验证生成的文件
        if output_path.exists() and output_path.stat().st_size > 1000:
            logger.info(f"EPUB文件已生成: {output_path}, 大小: {output_path.stat().st_size/1024:.2f} KB")
            return True
        else:
            logger.error(f"生成的EPUB文件失败或文件过小: {output_path}")
            return False
    except Exception as e:
        logger.error(f"创建EPUB文件时出错: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        try:
            if 'temp_dir' in locals() and isinstance(temp_dir, Path) and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
        return False


def merge_txt_to_epub(folder_path, output_path=None, author=None, novel_name=None, language='zh-CN'):
    """将文件夹中的txt文件合并为epub"""
    try:
        folder_path = Path(folder_path)
        
        # 检查文件夹是否存在
        if not folder_path.exists() or not folder_path.is_dir():
            logger.error(f"文件夹不存在或不是有效目录: {folder_path}")
            return None
        
        # 获取所有txt文件
        txt_files = [f.name for f in folder_path.iterdir() if f.suffix.lower() == '.txt']
        if not txt_files:
            logger.error(f"在 {folder_path} 中没有找到TXT文件")
            return None
        
        logger.info(f"在 {folder_path} 中找到 {len(txt_files)} 个TXT文件")
        
        # 提取章节信息
        book_name, chapters = extract_chapters(txt_files, folder_path, novel_name)
        
        if not book_name:
            logger.error("无法确定小说名称")
            return None
        
        if not chapters:
            logger.error("未能提取任何有效章节")
            return None
        
        # 如果未指定输出路径，则使用小说名称作为文件名
        if not output_path:
            output_path = folder_path / f"{book_name}_脱水.epub"
        
        # 创建EPUB书籍
        book = epub.EpubBook()
        book.set_title(book_name)
        book.set_language(language)
        
        if author:
            book.add_author(author)
        else:
            book.add_author("佚名")
        
        # 添加CSS
        style = '''
        @namespace epub "http://www.idpf.org/2007/ops";
        body { 
            font-family: "Noto Serif CJK SC", "Source Han Serif CN", SimSun, serif; 
            margin: 5%; 
            line-height: 1.5;
        }
        h1 { 
            text-align: center;
            font-size: 1.5em;
            margin: 1em 0;
        }
        p { 
            text-indent: 2em; 
            margin: 0.3em 0;
        }
        .cover {
            text-align: center;
            margin: 3em 0;
        }
        .author {
            text-align: center;
            margin: 1em 0;
        }
        .toc a {
            text-decoration: none;
            color: black;
        }
        '''
        css = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=style)
        book.add_item(css)
        
        # 添加封面页
        cover = epub.EpubHtml(title='封面', file_name='cover.xhtml', lang=language)
        cover.content = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <title>封面</title>
    <link rel="stylesheet" type="text/css" href="style.css" />
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
</head>
<body>
    <div class="cover">
        <h1 class="cover">{book_name}</h1>
        <p class="author">作者：{author if author else "佚名"}</p>
    </div>
</body>
</html>'''.encode("utf-8")
        book.add_item(cover)
        cover.add_link(href="style.css", rel="stylesheet", type="text/css")
        
        # 添加目录页
        toc_content = '<h1>目录</h1>\n<div class="toc">'
        for i, chapter in enumerate(chapters):
            safe_title = escape_html(chapter["title"])
            chapter_num = i + 1
            toc_content += f'<p><a href="chapter_{chapter_num}.xhtml">{safe_title}</a></p>\n'
        toc_content += '</div>'
        
        toc_page = epub.EpubHtml(title='目录', file_name='toc.xhtml', lang=language)
        toc_page.content = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <title>目录</title>
    <link rel="stylesheet" type="text/css" href="style.css" />
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
</head>
<body>
    {toc_content}
</body>
</html>'''.encode("utf-8")
        book.add_item(toc_page)
        toc_page.add_link(href="style.css", rel="stylesheet", type="text/css")
        
        # 添加章节
        epub_chapters = []
        success_count = 0
        
        for i, chapter in enumerate(chapters):
            try:
                content = read_txt_content(chapter['path'])
                
                # 格式化段落
                paragraphs_html = ""
                for p in content.split('\n'):
                    if p.strip():
                        paragraphs_html += f'<p>{escape_html(p.strip())}</p>\n'
                
                if not paragraphs_html.strip():
                    safe_title = escape_html(chapter['title'])
                    paragraphs_html = f"<p>（《{safe_title}》章节内容为空）</p>"
                
                # 创建章节
                chapter_id = f'chapter_{i+1}'
                file_name = f'{chapter_id}.xhtml'
                safe_title = escape_html(chapter['title'])
                
                c = epub.EpubHtml(uid=chapter_id, title=safe_title, file_name=file_name, lang=language)
                c.content = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <title>{safe_title}</title>
    <link rel="stylesheet" type="text/css" href="style.css" />
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
</head>
<body>
    <h1>{safe_title}</h1>
    {paragraphs_html}
</body>
</html>'''.encode("utf-8")
                
                c.add_link(href="style.css", rel="stylesheet", type="text/css")
                book.add_item(c)
                epub_chapters.append(c)
                success_count += 1
                
            except Exception as e:
                logger.error(f"添加章节 '{chapter['title']}' 时出错: {e}")
        
        if success_count == 0:
            logger.error("没有成功添加任何章节，无法继续生成EPUB")
            return None
        
        # 添加导航
        book.add_item(epub.EpubNcx())
        nav = epub.EpubNav()
        # ebooklib 0.17.1: 若 nav 文档 body 为空，write_epub 在生成导航页时会触发 lxml "Document is empty"
        # 提供最小 XHTML skeleton，后续由 writer 注入真正的 toc 内容。
        nav.content = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <title>Navigation</title>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
</head>
<body>
    <nav epub:type="toc" id="toc">
        <ol></ol>
    </nav>
</body>
</html>'''.encode("utf-8")
        nav.add_link(href="style.css", rel="stylesheet", type="text/css")
        book.add_item(nav)
        
        # 设置书籍脊柱（阅读顺序）
        spine = ['nav', cover, toc_page]
        for chapter in epub_chapters:
            spine.append(chapter)
        book.spine = spine
        
        # 设置目录
        book.toc = [
            epub.Link('cover.xhtml', '封面', 'cover'),
            epub.Link('toc.xhtml', '目录', 'toc')
        ]
        
        for i, chapter in enumerate(epub_chapters):
            chapter_num = i + 1
            book.toc.append(epub.Link(f'chapter_{chapter_num}.xhtml', chapter.title, f'chapter_{chapter_num}'))
        
        # 添加元数据
        unique_id = str(uuid.uuid4())
        book.add_metadata('DC', 'description', f'{book_name} - 由AI小说工具生成')
        book.add_metadata('DC', 'publisher', 'AI小说工具')
        book.add_metadata('DC', 'rights', '版权归原作者所有')
        book.add_metadata('DC', 'identifier', f'uuid:{unique_id}', {'id': 'unique-id'})
        
        # 创建EPUB文件
        if write_epub(book, output_path):
            logger.info(f"EPUB文件已成功生成: {output_path}")
            return str(output_path)
        else:
            logger.error("创建EPUB文件失败")
            return None
    except Exception as e:
        logger.error(f"合并TXT文件时出错: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return None


def main():
    """主函数，处理命令行参数并执行转换"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='将文件夹中的TXT文件合并为EPUB电子书')
    parser.add_argument('folder', help='包含TXT文件的文件夹路径')
    parser.add_argument('-o', '--output', help='输出EPUB文件的路径（可选）')
    parser.add_argument('-a', '--author', help='设置电子书的作者（可选）')
    parser.add_argument('-n', '--name', help='设置电子书的名称（可选，默认从文件名解析）')
    parser.add_argument('-l', '--language', default='zh-CN', help='设置电子书的语言（默认：zh-CN）')
    parser.add_argument('-v', '--verbose', action='store_true', help='显示详细日志')
    parser.add_argument('-q', '--quiet', action='store_true', help='仅显示错误信息')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        setup_logger(logging.DEBUG)
    elif args.quiet:
        setup_logger(logging.ERROR)
    
    # 执行转换
    result = merge_txt_to_epub(args.folder, args.output, args.author, args.name, args.language)
    
    # 返回状态码
    if result:
        logger.info(f"转换完成！EPUB文件已保存到: {result}")
        return 0
    else:
        logger.error("转换失败！")
        return 1


if __name__ == "__main__":
    exit(main()) 
