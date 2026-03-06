#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
小说处理工具的首页标签页
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .resources import get_icon
from .ui_components import apply_soft_shadow, create_badge


class MetricCard(QFrame):
    """首页摘要指标卡片。"""

    def __init__(self, value: str, label: str, description: str, parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        value_label = QLabel(value)
        value_label.setObjectName("metricValue")
        layout.addWidget(value_label)

        title_label = QLabel(label)
        title_label.setObjectName("metricLabel")
        layout.addWidget(title_label)

        description_label = QLabel(description)
        description_label.setObjectName("metricDescription")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)


class CardWidget(QFrame):
    """首页功能说明卡片。"""

    def __init__(self, title: str, icon_name: str, description: str, eyebrow: str, parent=None):
        super().__init__(parent)
        self.setObjectName("materialCard")
        self.setFrameShape(QFrame.StyledPanel)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        layout.addWidget(create_badge(eyebrow, "info"))

        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        icon_label = QLabel()
        icon_label.setObjectName("cardIcon")
        icon = get_icon(icon_name)
        if not icon.isNull():
            icon_label.setPixmap(icon.pixmap(24, 24))
        header_layout.addWidget(icon_label, alignment=Qt.AlignTop)

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        title_label.setWordWrap(True)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label, 1)

        layout.addLayout(header_layout)

        desc_label = QLabel(description)
        desc_label.setObjectName("cardDescription")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        apply_soft_shadow(self)


class HomeTab(QWidget):
    """首页标签页，介绍应用程序的使用方法。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("home_tab")
        self.init_ui()

    def init_ui(self):
        """初始化用户界面。"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(22)

        content_layout.addWidget(self._build_hero_card())
        content_layout.addWidget(self._build_section_title("标准工作流", "建议按以下顺序完成导入、脱水与重新打包。"))
        content_layout.addLayout(self._build_flow_cards())
        content_layout.addWidget(self._build_section_title("交付建议", "提前验证 API 与命名规范，可显著降低中途返工。"))
        content_layout.addLayout(self._build_guides())
        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        self.setLayout(main_layout)

    def _build_hero_card(self) -> QFrame:
        hero_card = QFrame()
        hero_card.setObjectName("heroCard")

        hero_layout = QVBoxLayout(hero_card)
        hero_layout.setContentsMargins(28, 28, 28, 28)
        hero_layout.setSpacing(18)

        hero_layout.addWidget(create_badge("AI 驱动工作台", "success"))

        title_label = QLabel("AI 小说处理实验室")
        title_label.setObjectName("heroTitle")
        title_label.setWordWrap(True)
        hero_layout.addWidget(title_label)

        description_label = QLabel(
            "从 EPUB 拆分、章节脱水到重新生成 EPUB，AINovelLab 将完整流程集中在同一个桌面工作台里，"
            "更适合长篇小说的批量处理与阶段性校验。"
        )
        description_label.setObjectName("heroDescription")
        description_label.setWordWrap(True)
        hero_layout.addWidget(description_label)

        metrics_layout = QGridLayout()
        metrics_layout.setHorizontalSpacing(14)
        metrics_layout.setVerticalSpacing(14)
        metrics_layout.addWidget(MetricCard("3 步", "标准链路", "拆分 → 脱水 → 合并，流程连续且便于追踪。"), 0, 0)
        metrics_layout.addWidget(MetricCard("混合 API", "弹性处理", "支持 Gemini 与兼容 OpenAI 协议的服务并行工作。"), 0, 1)
        metrics_layout.addWidget(MetricCard("批量章节", "可控范围", "支持按章节范围执行，适合长篇小说分批处理。"), 0, 2)
        hero_layout.addLayout(metrics_layout)

        apply_soft_shadow(hero_card, blur_radius=40, y_offset=14)
        return hero_card

    def _build_section_title(self, title: str, description: str) -> QFrame:
        section = QFrame()
        section.setObjectName("sectionHeader")

        layout = QVBoxLayout(section)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)

        description_label = QLabel(description)
        description_label.setObjectName("sectionDescription")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)

        return section

    def _build_flow_cards(self) -> QGridLayout:
        cards_layout = QGridLayout()
        cards_layout.setHorizontalSpacing(16)
        cards_layout.setVerticalSpacing(16)

        cards_layout.addWidget(
            CardWidget(
                "步骤一：EPUB 转 TXT",
                "book",
                "选择源 EPUB 后自动生成默认输出目录，并按章节或章节组拆分为结构化 TXT 文件，适合作为后续脱水的输入。",
                "准备原始章节",
            ),
            0,
            0,
        )
        cards_layout.addWidget(
            CardWidget(
                "步骤二：AI 脱水处理",
                "water",
                "选择 TXT 目录、限定章节范围并设置脱水比例区间，系统会自动调度可用 API 进行批量处理。",
                "核心处理环节",
            ),
            0,
            1,
        )
        cards_layout.addWidget(
            CardWidget(
                "步骤三：TXT 转 EPUB",
                "convert",
                "处理完成后可直接继承书名目录与输出路径，补齐标题和作者信息后重新生成 EPUB 文件。",
                "生成最终成品",
            ),
            1,
            0,
        )
        cards_layout.addWidget(
            CardWidget(
                "阶段校验：API 测试",
                "test",
                "在正式开始长任务前，建议先批量验证模型与密钥状态，避免中途因配置失效导致队列阻塞。",
                "提前排雷",
            ),
            1,
            1,
        )

        return cards_layout

    def _build_guides(self) -> QHBoxLayout:
        guides_layout = QHBoxLayout()
        guides_layout.setSpacing(16)

        guides_layout.addWidget(
            CardWidget(
                "配置建议",
                "settings",
                "优先准备多个可用 API 密钥，并在处理前完成一次全量测试；输出目录建议保持默认结构，便于各标签页自动承接路径。",
                "提高成功率",
            )
        )
        guides_layout.addWidget(
            CardWidget(
                "处理建议",
                "book",
                "长篇小说建议按章节范围分批脱水，保留原始 EPUB 备份，并避免手动修改系统生成的章节文件名，以确保顺序识别稳定。",
                "降低返工成本",
            )
        )

        return guides_layout
