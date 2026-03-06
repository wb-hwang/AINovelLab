#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
可复用的界面组件与样式辅助函数
"""

from typing import Sequence

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def apply_soft_shadow(widget: QWidget, blur_radius: int = 28, y_offset: int = 10) -> None:
    """为卡片类组件添加柔和阴影。"""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur_radius)
    shadow.setOffset(0, y_offset)
    shadow.setColor(QColor(15, 23, 42, 110))
    widget.setGraphicsEffect(shadow)


def style_button(button: QPushButton, role: str) -> None:
    """为按钮设置语义角色，配合 QSS 统一主题。"""
    button.setProperty("role", role)
    button.style().unpolish(button)
    button.style().polish(button)


def create_badge(text: str, tone: str = "default", parent: QWidget | None = None) -> QLabel:
    """创建带色彩语义的标签徽标。"""
    badge = QLabel(text, parent)
    badge.setObjectName("accentBadge")
    badge.setProperty("tone", tone)
    badge.setAlignment(Qt.AlignCenter)
    return badge


def create_stat_card(title: str, value: str, parent: QWidget | None = None) -> QFrame:
    """创建简洁的状态摘要卡片。"""
    card = QFrame(parent)
    card.setObjectName("statCard")

    layout = QVBoxLayout(card)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(2)

    title_label = QLabel(title)
    title_label.setObjectName("statCardTitle")
    title_label.setWordWrap(True)
    layout.addWidget(title_label)

    value_label = QLabel(value)
    value_label.setObjectName("statCardValue")
    value_label.setWordWrap(True)
    layout.addWidget(value_label)

    return card


def set_label_state(label: QLabel, state: str) -> None:
    """设置文本状态语义，统一反馈颜色。"""
    label.setProperty("state", state)
    label.style().unpolish(label)
    label.style().polish(label)


def show_info_message(parent: QWidget, title: str, message: str) -> None:
    """显示统一的信息弹窗。"""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setIcon(QMessageBox.Information)
    box.addButton("知道了", QMessageBox.AcceptRole)
    box.exec_()


def show_error_message(parent: QWidget, title: str, message: str) -> None:
    """显示统一的错误弹窗。"""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setIcon(QMessageBox.Critical)
    box.addButton("关闭", QMessageBox.RejectRole)
    box.exec_()


def show_warning_confirm(
    parent: QWidget,
    title: str,
    message: str,
    confirm_text: str = "继续",
    cancel_text: str = "取消",
) -> bool:
    """显示统一警告确认弹窗，返回是否确认。"""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setIcon(QMessageBox.Warning)
    cancel_button = box.addButton(cancel_text, QMessageBox.RejectRole)
    confirm_button = box.addButton(confirm_text, QMessageBox.AcceptRole)
    box.setDefaultButton(cancel_button)
    box.exec_()
    return box.clickedButton() == confirm_button


def show_completion_dialog(
    parent: QWidget,
    title: str,
    message: str,
    accept_text: str = "知道了",
    action_text: str | None = None,
) -> bool:
    """显示统一完成弹窗，返回是否点击了附加动作按钮。"""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setIcon(QMessageBox.Information)
    box.addButton(accept_text, QMessageBox.AcceptRole)

    action_button = None
    if action_text:
        action_button = box.addButton(action_text, QMessageBox.ActionRole)

    box.exec_()
    return action_button is not None and box.clickedButton() == action_button


def create_page_header(
    title: str,
    description: str,
    badges: Sequence[str | tuple[str, str]] | None = None,
) -> QFrame:
    """创建页面头部，提供统一的信息层级。"""
    header = QFrame()
    header.setObjectName("pageHeader")

    layout = QVBoxLayout(header)
    layout.setContentsMargins(24, 22, 24, 22)
    layout.setSpacing(12)

    title_label = QLabel(title)
    title_label.setObjectName("pageHeaderTitle")
    title_label.setWordWrap(True)
    layout.addWidget(title_label)

    description_label = QLabel(description)
    description_label.setObjectName("pageHeaderDescription")
    description_label.setWordWrap(True)
    layout.addWidget(description_label)

    normalized_badges = _normalize_badges(badges)
    if normalized_badges:
        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        for text, tone in normalized_badges:
            badge_row.addWidget(create_badge(text, tone))
        badge_row.addStretch()
        layout.addLayout(badge_row)

    apply_soft_shadow(header, blur_radius=34, y_offset=12)
    return header


def _normalize_badges(
    badges: Sequence[str | tuple[str, str]] | None,
) -> list[tuple[str, str]]:
    if not badges:
        return []

    normalized: list[tuple[str, str]] = []
    for item in badges:
        if isinstance(item, tuple):
            normalized.append(item)
        else:
            normalized.append((item, "default"))
    return normalized
