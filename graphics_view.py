# graphics_view.py

from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem
)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QWheelEvent, QMouseEvent, QPen

import numpy as np
from astropy.stats import sigma_clipped_stats
from photutils.detection import IRAFStarFinder

class GraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setMouseTracking(True)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self._scale = 1.0

        self._selecting = False
        self._selection_rect_item = None
        self._selection_origin = None
        self._callback = None
        self._image_data = None

        self._star_items_target = []
        self.coords_target = []

        self._star_items_comp = []
        self.coords_comp = []


    def set_detection_params(self, fwhm, threshold, sigma_clip):
        self.fwhm_value = fwhm
        self.threshold_value = threshold
        self.sigma_clipping_value = sigma_clip


    def set_image_data(self, data):
        self._image_data = data


    def wheelEvent(self, event: QWheelEvent):
        zoom_in_factor = 1.025
        zoom_out_factor = 0.99
        min_scale = 0.5
        max_scale = 12.5

        if event.angleDelta().y() > 0:
            factor = zoom_in_factor
        else:
            factor = zoom_out_factor

        new_scale = self._scale * factor
        if min_scale <= new_scale <= max_scale:
            self._scale = new_scale
            self.scale(factor, factor)


    def reset_zoom(self):
        # 모든 이미지마다 동일한 확대/축소 상태로 초기화
        self._scale = 1.0


    def set_region_selection_mode(self, callback, target_type="target"):
        """
        영역 선택 모드 활성화.
        target_type: "target"이면 빨간색/측광 대상, "comp"이면 파란색/비교성
        """
        self._callback = callback
        self._selecting = True
        self.setDragMode(QGraphicsView.NoDrag)
        self._region_target_type = target_type  # "target" or "comp"

        # 이전 선택 사각형이 남아 있으면 제거
        if self._selection_rect_item is not None:
            self.scene().removeItem(self._selection_rect_item)
            self._selection_rect_item = None

        if self._region_target_type == "target":
            self.clear_target_stars()
        else:
            self.clear_comp_stars()

        # self.textBrowser.append(f"[INFO] 영역 선택 모드 활성화 ({'측광 대상' if target_type == 'target' else '비교성'})")
       

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._selecting and self._selection_origin is not None and self._selection_rect_item is not None:
            current_pos = self.mapToScene(event.pos())
            rect = QRectF(self._selection_origin, current_pos).normalized()
            self._selection_rect_item.setRect(rect)
        else:
            super().mouseMoveEvent(event)


    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._selecting and event.button() == Qt.LeftButton:
            self._selecting = False
            self.setDragMode(QGraphicsView.ScrollHandDrag)

            rect = self._selection_rect_item.rect()
            self.scene().removeItem(self._selection_rect_item)
            self._selection_rect_item = None

            x1, y1, w, h = rect.x(), rect.y(), rect.width(), rect.height()
            if self._image_data is None:
                # self.textBrowser.append("[WARN] 이미지 데이터가 없음")
                return

            sub_img = self._image_data[int(y1):int(y1 + h), int(x1):int(x1 + w)]
            if sub_img.size == 0:
                # self.textBrowser.append("[WARN] 선택 영역이 유효하지 않음")
                return

            # 더 나은 별 검출을 위해 photutils의 IRAFStarFinder 사용 (더 정교한 PSF 기반)
            mean, median, std = sigma_clipped_stats(sub_img, sigma=self.sigma_clipping_value)
            # IRAFStarFinder는 PSF의 sigma(표준편차) 단위로 입력받음 (fwhm = 2.3548 * sigma)
            sigma_psf = self.fwhm_value / 2.3548
            star_finder = IRAFStarFinder(threshold=self.threshold_value * std, fwhm=self.fwhm_value, sigma_radius=sigma_psf)
            sources = star_finder(sub_img - median)

            if sources is not None:
                for x, y in zip(sources['xcentroid'], sources['ycentroid']):
                    abs_x = x1 + x
                    abs_y = y1 + y

                    # 시각화 (얇은 뚫린 원)
                    radius = 6
                    pen = QPen(Qt.red)
                    pen.setWidthF(0.5)
                    ellipse = QGraphicsEllipseItem(abs_x - radius, abs_y - radius, radius * 2, radius * 2)
                    ellipse.setPen(pen)
                    ellipse.setBrush(Qt.NoBrush)
                    self.scene().addItem(ellipse)

                    # '측광 대상' 텍스트 추가
                    if self._region_target_type == "target":
                        text_item = QGraphicsTextItem("측광 대상")
                        text_item.setDefaultTextColor(Qt.red)
                        pen = QPen(Qt.red)
                    else:
                        text_item = QGraphicsTextItem("비교성")
                        text_item.setDefaultTextColor(Qt.blue)
                        pen = QPen(Qt.blue)
                    
                    pen.setWidthF(0.5)
                    ellipse.setPen(pen)
                    text_item.setPos(abs_x + radius + 2, abs_y - radius)
                    self.scene().addItem(text_item)

                    # 마커와 텍스트를 리스트에 저장
                    if self._region_target_type == "target":
                        self._star_items_target.append((ellipse, text_item))
                        self.coords_target.append((abs_x, abs_y))
                    else:
                        self._star_items_comp.append((ellipse, text_item))
                        self.coords_comp.append((abs_x, abs_y))

            if self._region_target_type == "target":
                # self.textBrowser.append(f"[INFO] 감지된 측광 대상 별 개수: {len(self.coords_target)}")
                pass
            else:
                # self.textBrowser.append(f"[INFO] 감지된 비교성 별 개수: {len(self.coords_comp)}")
                pass

            # 콜백 호출
            if self._callback:
                if self._region_target_type == "target":
                    self._callback(self.coords_target)
                else:
                    self._callback(self.coords_comp)
        else:
            super().mouseReleaseEvent(event)


    def enable_manual_star_selection(self, callback, target_type="target"):
        """
        수동 별 선택 모드 활성화. 사용자가 마우스 클릭으로 별 위치를 직접 지정할 수 있습니다.
        선택된 별 마커는 clear_detected_stars()로 제거할 수 있습니다.
        """
        self._manual_star_callback = callback
        self._manual_star_selecting = True
        self.setDragMode(QGraphicsView.NoDrag)
        
        self._region_target_type = target_type  # "target" or "comp"
        
        if self._region_target_type == "target":
            self.clear_target_stars()
        else:
            self.clear_comp_stars()

        # self.textBrowser.append(f"[INFO] 수동 별 선택 모드 활성화 ({'측광 대상' if target_type == 'target' else '비교성'})")


    def mousePressEvent(self, event: QMouseEvent):
        # 수동 별 선택 모드가 우선
        if getattr(self, "_manual_star_selecting", False) and event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            x, y = np.float64(scene_pos.x()), np.float64(scene_pos.y())

            # 마커 추가
            radius = 6
            ellipse = QGraphicsEllipseItem(x - radius, y - radius, radius * 2, radius * 2)
            ellipse.setBrush(Qt.NoBrush)
            self.scene().addItem(ellipse)
            
            if self._region_target_type == "target":
                text_item = QGraphicsTextItem("측광 대상")
                text_item.setDefaultTextColor(Qt.red)
                text_item.setPos(x + radius + 2, y - radius)
                self.scene().addItem(text_item)
                pen = QPen(Qt.red)
            else:
                text_item = QGraphicsTextItem("비교성")
                text_item.setDefaultTextColor(Qt.blue)
                text_item.setPos(x + radius + 2, y - radius)
                self.scene().addItem(text_item)
                pen = QPen(Qt.blue)

            pen.setWidthF(0.5)
            ellipse.setPen(pen)

            # 마커와 텍스트를 리스트에 저장
            if self._region_target_type == "target":
                self._star_items_target.append((ellipse, text_item))
                self.coords_target.append((x, y))
            else:
                self._star_items_comp.append((ellipse, text_item))
                self.coords_comp.append((x, y))

            # self.textBrowser.append(f"[INFO] 수동 선택 별 좌표: ({x:.1f}, {y:.1f})")

            # 콜백 호출
            if self._manual_star_callback:
                if self._region_target_type == "target":
                    self._manual_star_callback(self.coords_target)
                else:
                    self._manual_star_callback(self.coords_comp)

            # 한 번 선택 후 일반 상태로 복귀
            self._manual_star_selecting = False
            self.setDragMode(QGraphicsView.ScrollHandDrag)

        # 자동 선택(영역 지정) 모드
        elif self._selecting and event.button() == Qt.LeftButton:
            self._selection_origin = self.mapToScene(event.pos())
            self._selection_rect_item = QGraphicsRectItem()
            self._selection_rect_item.setPen(QPen(Qt.green, 1, Qt.DashLine))
            self.scene().addItem(self._selection_rect_item)
        else:
            super().mousePressEvent(event)


    def clear_target_stars(self):
        """측광 대상 별 마커와 텍스트, 좌표 정보를 모두 제거합니다."""
        if hasattr(self, "_star_items_target"):
            for ellipse, text_item in self._star_items_target:
                self.scene().removeItem(ellipse)
                self.scene().removeItem(text_item)
            self._star_items_target.clear()
            # self.textBrowser.append("[INFO] 측광 대상 별 마커를 모두 제거했습니다.")
        # 좌표 정보도 삭제
        if hasattr(self, "coords_target"):
            self.coords_target.clear()


    def clear_comp_stars(self):
        """비교성 별 마커와 텍스트, 좌표 정보를 모두 제거합니다."""
        if hasattr(self, "_star_items_comp"):
            for ellipse, text_item in self._star_items_comp:
                self.scene().removeItem(ellipse)
                self.scene().removeItem(text_item)
            self._star_items_comp.clear()
            # self.textBrowser.append("[INFO] 비교성 별 마커를 모두 제거했습니다.")
        # 좌표 정보도 삭제
        if hasattr(self, "coords_comp"):
            self.coords_comp.clear()

