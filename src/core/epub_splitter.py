#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EPUB分割器 - 将EPUB电子书分割成多个TXT文件

这个脚本可以将EPUB电子书文件按章节分割成多个TXT文件，
便于在不同设备上阅读或进行其他处理。
"""

import os
import re
import argparse
import logging
from pathlib import Path
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

from .utils import get_safe_filename

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


def html_to_text(html_content):
    """
    将HTML内容转换为纯文本
    
    Args:
        html_content: HTML格式的内容字符串
        
    Returns:
        str: 提取并格式化后的纯文本
    """
    try:
        # 优先尝试使用XML解析器（适用于EPUB中的XML文档）
        soup = BeautifulSoup(html_content, 'xml')
    except Exception as e:
        # 如果XML解析失败，回退到原来的lxml解析器
        logger.debug(f"XML解析失败，回退到lxml: {e}")
        soup = BeautifulSoup(html_content, 'lxml')
    
    # 移除脚本和样式元素
    for script in soup(["script", "style"]):
        script.extract()
    
    # 获取文本
    text = soup.get_text()
    
    # 处理多余的空行和空格
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = '\n'.join(chunk for chunk in chunks if chunk)
    
    return text


def extract_title_from_html(html_content):
    """
    从HTML内容中提取章节标题
    
    Args:
        html_content: HTML格式的内容字符串
        
    Returns:
        str or None: 提取的章节标题，如果无法提取则返回None
    """
    try:
        # 优先尝试使用XML解析器（适用于EPUB中的XML文档）
        soup = BeautifulSoup(html_content, 'xml')
    except Exception as e:
        # 如果XML解析失败，回退到原来的lxml解析器
        logger.debug(f"XML解析失败，回退到lxml: {e}")
        soup = BeautifulSoup(html_content, 'lxml')
    
    # 查找标题策略1: 标准HTML标题标签
    for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        title_tag = soup.find(tag)
        if title_tag and title_tag.get_text().strip():
            return title_tag.get_text().strip()
    
    # 查找标题策略2: 特定class或id
    title_candidates = []
    title_pattern = re.compile(r'(chapter|title|heading)', re.IGNORECASE)
    
    # 查找可能包含"chapter"、"title"、"heading"等关键词的class
    for element in soup.find_all(class_=title_pattern):
        text = element.get_text().strip()
        if text:
            title_candidates.append(text)
    
    # 查找可能包含"chapter"、"title"、"heading"等关键词的id
    for element in soup.find_all(id=title_pattern):
        text = element.get_text().strip()
        if text:
            title_candidates.append(text)
    
    # 查找标题策略3: 章节模式文本
    chapter_pattern = re.compile(r'(第\s*[0-9一二三四五六七八九十百千万]+\s*[章节]|Chapter\s+\d+)', re.IGNORECASE)
    
    for element in soup.find_all(string=chapter_pattern):
        parent = element.parent
        if parent and parent.get_text().strip():
            title_candidates.append(parent.get_text().strip())
    
    # 如果找到了候选标题，返回最长的一个(通常最完整)
    if title_candidates:
        return max(title_candidates, key=len)
    
    # 如果未找到标题，返回None
    return None


def get_spine_order(book):
    """
    获取EPUB书籍的spine顺序，这反映了阅读的正确顺序
    
    Args:
        book: EPUB书籍对象
    
    Returns:
        dict: 文档ID到序号的映射
    """
    spine_ids = [item[0] for item in book.spine]
    id_to_index = {id: index for index, id in enumerate(spine_ids)}
    return id_to_index


def clean_content(content, title):
    """
    清理章节内容，移除可能重复的标题
    
    Args:
        content: 章节内容
        title: 章节标题
    
    Returns:
        str: 清理后的内容
    """
    if not title or not content:
        return content
        
    # 尝试移除内容开头的标题
    lines = content.split('\n')
    clean_lines = []
    title_removed = False
    title_lower = title.lower().strip()
    
    # 检查前几行是否包含标题
    for line in lines:
        line_stripped = line.strip()
        line_lower = line_stripped.lower()
        
        # 如果行与标题完全匹配或包含标题
        if not title_removed and (line_lower == title_lower or title_lower in line_lower):
            title_removed = True
            continue
        clean_lines.append(line)
    
    return '\n'.join(clean_lines)


def sort_items_by_spine(items, spine_order):
    """
    按照spine顺序排序文档
    
    Args:
        items: 文档项列表
        spine_order: spine顺序字典
    
    Returns:
        list: 排序后的文档列表
    """
    def get_item_order(item):
        # 首先尝试通过ID在spine中查找顺序
        item_id = item.get_id()
        if item_id in spine_order:
            return spine_order[item_id]
        # 如果ID不在spine中，尝试通过文件名中的数字排序
        digits = ''.join(filter(str.isdigit, item_id))
        return int(digits) if digits else float('inf')
    
    try:
        # 尝试按spine顺序排序
        return sorted(items, key=get_item_order)
    except Exception as e:
        logger.warning(f"按spine顺序排序失败 ({e})，尝试按文件名中的数字排序")
        # 回退方案：按文件名中的数字排序
        return sorted(items, key=lambda x: int(''.join(filter(str.isdigit, x.get_id()))) 
                     if any(c.isdigit() for c in x.get_id()) else float('inf'))


def extract_toc_titles(book):
    """
    从EPUB的目录(TOC)中提取章节标题映射
    
    Args:
        book: EPUB book对象
    
    Returns:
        dict: 文件名到标题的映射字典
    """
    toc_map = {}

    def normalize_href_to_filename(href):
        """将TOC链接标准化为文件名键（去路径、去锚点）"""
        normalized_href = href.split('#')[0]
        return normalized_href.split('/')[-1]
    
    def process_toc_items(toc_items):
        """递归处理TOC项目"""
        for item in toc_items:
            if hasattr(item, 'href') and hasattr(item, 'title'):
                filename = normalize_href_to_filename(item.href)
                toc_map[filename] = item.title.strip()
            elif isinstance(item, tuple) and len(item) == 2:
                # 处理嵌套的TOC结构
                section, children = item
                if hasattr(section, 'href') and hasattr(section, 'title'):
                    filename = normalize_href_to_filename(section.href)
                    toc_map[filename] = section.title.strip()
                if children:
                    process_toc_items(children)
    
    try:
        if book.toc:
            if isinstance(book.toc, (list, tuple)):
                process_toc_items(book.toc)
            logger.info(f"从TOC中提取了 {len(toc_map)} 个章节标题")
    except Exception as e:
        logger.warning(f"提取TOC标题时出错: {e}")
    
    return toc_map


def extract_chapters(items, toc_map=None):
    """
    从HTML文档中提取章节内容
    
    Args:
        items: 排序后的文档项列表
        toc_map: 可选的TOC标题映射字典
    
    Returns:
        list: 包含(章节标题, 章节内容)元组的列表
    """
    chapters = []
    
    for index, item in enumerate(items):
        try:
            # 解码HTML内容
            html_content = item.get_content().decode('utf-8')
            
            # 优先从TOC获取章节标题
            chapter_title = None
            item_name = item.get_name()
            item_filename = item_name.split('#')[0].split('/')[-1]
            
            if toc_map and item_filename in toc_map:
                chapter_title = toc_map[item_filename]
                logger.debug(f"从TOC获取标题: {chapter_title}")
            
            # 如果TOC中没有，尝试从HTML内容提取
            if not chapter_title:
                chapter_title = extract_title_from_html(html_content)
            
            # 如果仍无法提取标题，使用简洁的回退格式
            if not chapter_title:
                chapter_title = f"Chapter_{index + 1}"
                logger.debug(f"使用回退标题: {chapter_title}")
            
            # 提取章节文本
            chapter_text = html_to_text(html_content)
            
            # 清理章节内容，移除可能重复的标题
            chapter_text = clean_content(chapter_text, chapter_title)
            
            # 确保章节内容不为空
            if chapter_text.strip():
                chapters.append((chapter_title, chapter_text))
                logger.info(f"已提取章节: {chapter_title}")
            else:
                logger.warning(f"跳过空章节: {chapter_title}")
        except Exception as e:
            logger.warning(f"处理文档 {item.get_id()} 时出错: {e}")
    
    return chapters


def generate_output_filename(output_dir, book_title, file_index, chunk_chapters, 
                           use_range_in_filename, start_chapter, end_chapter):
    """
    生成输出文件名
    
    Args:
        output_dir: 输出目录
        book_title: 书名
        file_index: 文件索引
        chunk_chapters: 当前文件包含的章节列表
        use_range_in_filename: 是否使用章节范围
        start_chapter: 起始章节编号
        end_chapter: 结束章节编号
    
    Returns:
        str: 输出文件完整路径
    """
    if len(chunk_chapters) == 1:
        # 当只有一个章节时，使用"书名_[序号]_章节名.txt"格式
        chapter_title = get_safe_filename(chunk_chapters[0][0])
        return os.path.join(output_dir, f"{book_title}_[{file_index}]_{chapter_title}.txt")
    elif use_range_in_filename and len(chunk_chapters) > 1:
        # 当有多个章节时，使用章节范围
        return os.path.join(output_dir, f"{book_title}_[{start_chapter}-{end_chapter}].txt")
    else:
        # 简单格式
        return os.path.join(output_dir, f"{book_title}_[{file_index}].txt")


def write_chapters_to_file(output_filename, chunk_chapters):
    """
    将章节内容写入文件
    
    Args:
        output_filename: 输出文件名
        chunk_chapters: 要写入的章节列表
    """
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            for idx, (title, content) in enumerate(chunk_chapters):
                # 直接写入章节内容
                f.write(content)
                
                # 只在章节之间添加分隔符，最后一个章节不添加
                if idx < len(chunk_chapters) - 1:
                    f.write("\n\n" + "-" * 50 + "\n\n")
                else:
                    f.write("\n")
        
        logger.info(f"已创建文件: {output_filename} (包含 {len(chunk_chapters)} 章节)")
        return True
    except Exception as e:
        logger.error(f"写入文件 {output_filename} 失败: {e}")
        return False


def split_epub(epub_path, output_dir, chapters_per_file=100, use_range_in_filename=True):
    """
    分割EPUB文件，每个输出文件包含指定数量的章节
    
    Args:
        epub_path: EPUB文件路径
        output_dir: 输出目录
        chapters_per_file: 每个txt文件中包含的章节数，默认为100
        use_range_in_filename: 是否在文件名中使用章节范围，默认为True
        
    Returns:
        bool: 操作是否成功
    """
    try:
        # 创建输出目录（如果不存在）
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 读取EPUB文件
        logger.info(f"正在读取EPUB文件: {epub_path}")
        book = epub.read_epub(epub_path)
        
        # 使用EPUB文件名作为书名
        book_title = Path(epub_path).stem
        book_title = get_safe_filename(book_title)
        
        logger.info(f"处理书籍: {book_title}")
        
        # 获取所有HTML文档
        items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        logger.info(f"总共找到 {len(items)} 个文档")
        
        if not items:
            logger.error("EPUB文件不包含任何文档")
            return False
        
        # 获取spine顺序并排序文档
        spine_order = get_spine_order(book)
        items = sort_items_by_spine(items, spine_order)
        
        # 从TOC提取章节标题映射
        toc_map = extract_toc_titles(book)
        
        # 提取章节
        chapters = extract_chapters(items, toc_map)
        
        logger.info(f"成功提取 {len(chapters)} 个章节")
        
        if not chapters:
            logger.error("未能提取任何章节。请检查EPUB文件是否有效。")
            return False
        
        # 按指定数量分割章节并写入txt文件
        successful_files = 0
        total_files = (len(chapters) + chapters_per_file - 1) // chapters_per_file
        
        for i in range(0, len(chapters), chapters_per_file):
            chunk_chapters = chapters[i:i+chapters_per_file]
            file_index = i // chapters_per_file + 1
            
            start_chapter = i + 1
            end_chapter = min(i + chapters_per_file, len(chapters))
            
            # 生成输出文件名
            output_filename = generate_output_filename(
                output_dir, book_title, file_index, chunk_chapters, 
                use_range_in_filename, start_chapter, end_chapter
            )
            
            # 写入章节到文件
            if write_chapters_to_file(output_filename, chunk_chapters):
                successful_files += 1
        
        logger.info(f"总共分割为 {total_files} 个文件，成功生成 {successful_files} 个文件")
        return successful_files == total_files
        
    except Exception as e:
        logger.error(f"分割EPUB文件时出错: {e}")
        return False


def prepare_output_directory(args):
    """
    准备输出目录
    
    Args:
        args: 命令行参数
    
    Returns:
        str: 输出目录路径
    """
    # 如果没有指定输出目录，则自动创建与EPUB文件同名的目录下的splitted目录
    if args.output is None:
        # 获取EPUB文件名（不带扩展名）
        epub_basename = Path(args.epub_file).stem
        # 创建同名目录
        base_dir = Path.cwd() / epub_basename
        # 创建splitted子目录
        output_dir = base_dir / "splitted"
        # 确保目录存在
        base_dir.mkdir(exist_ok=True)
    else:
        output_dir = Path(args.output)
    
    # 清空输出目录中的所有文件（如果目录存在）
    if output_dir.exists():
        files = [f for f in output_dir.iterdir() if f.is_file()]
        if files and not args.no_clean:
            logger.info(f"清空目录 {output_dir} 中的 {len(files)} 个文件...")
            for file in files:
                try:
                    file.unlink()
                except Exception as e:
                    logger.warning(f"无法删除文件 {file.name}: {e}")
    
    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    return str(output_dir)


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='将EPUB文件按章节分割成多个TXT文件')
    parser.add_argument('epub_file', help='EPUB文件路径')
    parser.add_argument('-o', '--output', default=None, help='输出目录 (默认: 自动创建与EPUB文件同名的目录下的splitted目录)')
    parser.add_argument('-c', '--chapters', type=int, default=100, help='每个TXT文件包含的章节数 (默认: 100)')
    parser.add_argument('-r', '--use-range', action='store_true', help='在文件名中使用章节范围 (如: 书名_[1-100].txt)')
    parser.add_argument('-s', '--simple', action='store_true', help='使用简单文件名格式 (如: 书名_[1].txt)')
    parser.add_argument('-n', '--no-clean', action='store_true', help='不清空输出目录')
    parser.add_argument('-v', '--verbose', action='store_true', help='显示详细日志')
    parser.add_argument('-q', '--quiet', action='store_true', help='仅显示错误信息')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        setup_logger(logging.DEBUG)
    elif args.quiet:
        setup_logger(logging.ERROR)
    
    # 检查EPUB文件是否存在
    if not Path(args.epub_file).is_file():
        logger.error(f"错误: 找不到EPUB文件 '{args.epub_file}'")
        return 1
    
    # 准备输出目录
    output_dir = prepare_output_directory(args)
    
    # 确定是否在文件名中使用章节范围
    use_range_in_filename = args.use_range and not args.simple
    
    # 显示处理信息
    logger.info(f"开始处理EPUB文件: {args.epub_file}")
    logger.info(f"输出目录: {output_dir}")
    logger.info(f"每个文件的章节数: {args.chapters}")
    
    # 分割EPUB文件
    success = split_epub(args.epub_file, output_dir, args.chapters, use_range_in_filename)
    
    if success:
        logger.info(f"分割完成! 文件已保存到 {output_dir} 目录")
        return 0
    else:
        logger.error(f"分割过程中出现错误，请检查日志")
        return 1


if __name__ == '__main__':
    exit_code = main()
    exit(exit_code) 
