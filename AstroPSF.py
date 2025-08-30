# PySide6 및 기타 필요한 모듈
import sys
import numpy as np
import warnings
from scipy.optimize import curve_fit

from astropy.io import fits
from astropy.table import Table

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QGraphicsScene, QGraphicsPixmapItem
)
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt, QTimer

from ui_PSF import Ui_MainWindow
from graphics_view import GraphicsView  # 사용자 정의 QGraphicsView

from photutils.psf import PSFPhotometry, CircularGaussianPRF
from photutils.background import LocalBackground, MMMBackground
from astropy.modeling.fitting import TRFLSQFitter


# ------------------------------------------------
# 메인 윈도우 클래스 정의
# ------------------------------------------------


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, *args, obj=None, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle("AstroPSF")

        self.textBrowser.append("[INFO] AstroPSF 프로그램 시작")

        # 1. layout에서 기존 graphicsView 제거
        self.graphicsView.setParent(None)

        # 2. 새 GraphicsView 인스턴스 생성
        self.graphicsView = GraphicsView(self.centralwidget)

        # 3. 기존 layout에 다시 삽입
        self.horizontalLayout.addWidget(self.graphicsView)

        # 4. 디버깅 확인
        # print("GraphicsView type:", type(self.graphicsView))

        self.scene = QGraphicsScene(self)
        self.graphicsView.setScene(self.scene)
        self.pixmap_item = None

        self.pushButton.clicked.connect(self.f1)
        self.pushButton_2.clicked.connect(self.f2)
        self.pushButton_3.clicked.connect(self.f3)
        self.pushButton_4.clicked.connect(self.f4)
        self.pushButton_5.clicked.connect(self.f5)
        self.pushButton_6.clicked.connect(self.f6)
        self.pushButton_7.clicked.connect(self.f7)
        self.pushButton_8.clicked.connect(self.f8)

        # textBrowser 폰트 사이즈 설정 예시
        font = self.textBrowser.font()
        font.setPointSize(10)  # 원하는 폰트 크기로 변경
        self.textBrowser.setFont(font)

        # 전역에서 사용할 변수 초기화
        self.fwhm_value = self.doubleSpinBox.value()
        self.threshold_value = self.doubleSpinBox_2.value()
        self.sigma_clipping_value = self.doubleSpinBox_3.value()

        self.doubleSpinBox.valueChanged.connect(self.FWHM)
        self.doubleSpinBox_2.valueChanged.connect(self.Threshold)
        self.doubleSpinBox_3.valueChanged.connect(self.sigma_clipping)

        self.graphicsView.set_detection_params(
            self.fwhm_value, self.threshold_value, self.sigma_clipping_value
        )

        # 비교성 겉보기 등급을 전역 변수로 선언
        self.comp_mag = self.lineEdit_3.text()  # lineEdit_3에 입력된 값을 가져옴
        try:
            self.comp_mag = float(self.comp_mag)
        except ValueError:
            self.comp_mag = 10.00  # 기본값 또는 오류 처리

        self.lineEdit_3.textChanged.connect(self.update_comp_mag)

        # PSF FWHM을 전역 변수로 선언
        self.psf_fwhm = self.lineEdit.text()  # lineEdit에 입력된 값을 가져옴
        try:
            self.psf_fwhm = float(self.psf_fwhm)
        except ValueError:
            self.psf_fwhm = 5.00  # 기본값 또는 오류 처리

        self.lineEdit.textChanged.connect(self.update_psf_fwhm)

    def update_psf_fwhm(self, text):
        try:
            self.psf_fwhm = float(text)
            self.textBrowser.append(f"[INFO] PSF FWHM 업데이트: {self.psf_fwhm}")
        except ValueError:
            self.textBrowser.append("[ERROR] PSF FWHM 입력 오류, 기본값 5 사용")
            self.psf_fwhm = 5.00  # 기본값 또는 오류 처리

    def update_comp_mag(self, text):
        try:
            self.comp_mag = float(text)
            self.textBrowser.append(f"[INFO] 비교성 겉보기 등급 업데이트: {self.comp_mag}")
        except ValueError:
            self.textBrowser.append("[ERROR] 비교성 겉보기 등급 입력 오류, 기본값 10 사용")
            self.comp_mag = 10.00  # 기본값 또는 오류 처리

    def FWHM(self, value):
        self.fwhm_value = value
        self.graphicsView.set_detection_params(
            self.fwhm_value, self.threshold_value, self.sigma_clipping_value
        )

    def Threshold(self, value):
        self.threshold_value = value
        self.graphicsView.set_detection_params(
            self.fwhm_value, self.threshold_value, self.sigma_clipping_value
        )

    def sigma_clipping(self, value):
        self.sigma_clipping_value = value
        self.graphicsView.set_detection_params(
            self.fwhm_value, self.threshold_value, self.sigma_clipping_value
        )

    def load_fits_to_graphicsview(self, path):
        data = fits.getdata(path)
        data = np.nan_to_num(data)
        vmin, vmax = np.percentile(data, [5, 99])
        clipped = np.clip(data, vmin, vmax)
        normed = ((clipped - vmin) / (vmax - vmin) * 255).astype(np.uint8)

        height, width = normed.shape
        qimage = QImage(normed.data, width, height, width, QImage.Format_Grayscale8)
        pixmap = QPixmap.fromImage(qimage)

        if self.pixmap_item:
            self.scene.removeItem(self.pixmap_item)

        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)
        self.graphicsView.setSceneRect(self.scene.itemsBoundingRect())
        self.graphicsView.resetTransform()
        
        QTimer.singleShot(0, lambda: self.graphicsView.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio))

        self.graphicsView.set_image_data(data)

        self.graphicsView.reset_zoom()

    def f1(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open FITS File", "", "FITS Files (*.fits *.fit)")
        if file_path:
            self.load_fits_to_graphicsview(file_path)

    def f2(self):
        self.textBrowser.append("[INFO] 측광 대상 자동 선택 모드 진입")
        self.graphicsView.set_region_selection_mode(self.target_coords, target_type="target")
        
    def f3(self):
        self.textBrowser.append("[INFO] 비교성 자동 선택 모드 진입")
        self.graphicsView.set_region_selection_mode(self.comp_coords, target_type="comp")

    def f5(self):
        self.textBrowser.append("[INFO] 측광 대상 선택 취소")
        self.graphicsView.clear_target_stars()

    def f6(self):
        self.textBrowser.append("[INFO] 비교성 선택 취소")
        self.graphicsView.clear_comp_stars()

    def f7(self):
        self.textBrowser.append("[INFO] 측광 대상 수동 선택 모드 진입")
        self.graphicsView.enable_manual_star_selection(self.target_coords, target_type="target")

    def f8(self):
        self.textBrowser.append("[INFO] 비교성 수동 선택 모드 진입")
        self.graphicsView.enable_manual_star_selection(self.comp_coords, target_type="comp")

    def target_coords(self, coords):
        self._target_coords = []
        self._target_coords = coords
        # print(self._target_coords)
        return self._target_coords

    def comp_coords(self, coords):
        self._comp_coords = []
        self._comp_coords = coords
        # print(self._comp_coords)
        return self._comp_coords

    def f4(self):
        try:
            data = self.graphicsView._image_data
            if data is None:
                self.textBrowser.append("[ERROR] 이미지 데이터가 없습니다.")
                return

            # 좌표 수집 및 분리
            target_coords = getattr(self, "_target_coords", [])
            comp_coords = getattr(self, "_comp_coords", [])

            if not target_coords:
                self.textBrowser.append("[ERROR] 측광 대상 좌표가 없습니다.")
                return
            if not comp_coords:
                self.textBrowser.append("[ERROR] 비교성 좌표가 없습니다.")
                return
            
            # 예: 이미지와 별 좌표가 주어졌을 때
            # 첫 번째 타겟 좌표를 사용
            x0, y0 = target_coords[0]
            fwhm_result = self.estimate_fwhm_1d_profile(data, x0=x0, y0=y0, size=31)

            self.textBrowser.append(f"측광 대상 FWHM_x: {fwhm_result['fwhm_x']:.2f}")
            self.textBrowser.append(f"측광 대상 FWHM_y: {fwhm_result['fwhm_y']:.2f}")

            x1, y1 = comp_coords[0]
            fwhm_comp_result = self.estimate_fwhm_1d_profile(data, x0=x1, y0=y1, size=31)

            self.textBrowser.append(f"비교성 FWHM_x: {fwhm_comp_result['fwhm_x']:.2f}")
            self.textBrowser.append(f"비교성 FWHM_y: {fwhm_comp_result['fwhm_y']:.2f}")
            
            fwhm_values = [
                fwhm_result['fwhm_x'],
                fwhm_result['fwhm_y'],
                fwhm_comp_result['fwhm_x'],
                fwhm_comp_result['fwhm_y']
            ]
            fwhm = np.nanmean(fwhm_values)

            self.lineEdit.setText(f"{fwhm:.3f}")

            psf_model = CircularGaussianPRF(fwhm=fwhm)
            psf_model.fwhm.fixed = True


            def ensure_odd(n):
                return int(n) if int(n) % 2 == 1 else int(n) + 1

            inner_radius = int(round(fwhm * 2))
            outer_radius = int(round(fwhm * 4))
            fit_size = ensure_odd(round(fwhm * 6))
            fit_shape = (fit_size, fit_size)

            # 지역 배경 추정 설정
            bkg_est = LocalBackground(
                inner_radius=inner_radius,
                outer_radius=outer_radius,
                bkg_estimator=MMMBackground()
            )

            # 각각 Table로 변환
            target_positions = Table(rows=target_coords, names=["x_0", "y_0"])
            comp_positions = Table(rows=comp_coords, names=["x_0", "y_0"])
            
            # PSF 측광 객체 생성
            phot = PSFPhotometry(
                psf_model=psf_model,
                fit_shape=fit_shape,
                finder=None,
                fitter=TRFLSQFitter(),
                localbkg_estimator=bkg_est,
                aperture_radius=fwhm * 2,
                progress_bar=False,
            )
            
            # PSF 측광 수행
            target_result = phot(data, init_params=target_positions)
            comp_result = phot(data, init_params=comp_positions)

            # print("[INFO] 측광 대상 결과:")
            # print(target_result["id", "x_fit", "y_fit", "flux_fit"])

            # print("[INFO] 비교성 결과:")
            # print(comp_result["id", "x_fit", "y_fit", "flux_fit"])

            # 겉보기 등급 계산 예시 (비교성의 등급이 comp_mag라면)
            # m_target = m_comp - 2.5 * log10(flux_target / flux_comp)
            # 아래는 첫 번째 별만 예시로 계산
            if len(target_result) > 0 and len(comp_result) > 0:
                flux_target = target_result["flux_fit"][0]
                flux_comp = comp_result["flux_fit"][0]
                comp_mag = self.comp_mag
                m_target = comp_mag - 2.5 * np.log10(flux_target / flux_comp)
                self.lineEdit_4.setText(f"{m_target:.3f}")
                self.textBrowser.append(f"[INFO] 측광 대상의 겉보기 등급: {m_target:.3f}")

        except Exception as e:
            self.textBrowser.append(f"[ERROR] PSF photometry 실패: {e}")
    

    def gaussian_1d(self, x, amplitude, mean, sigma, offset):
        return amplitude * np.exp(-(x - mean)**2 / (2 * sigma**2)) + offset


    def estimate_fwhm_1d_profile(self, image, x0, y0, size=21):
        """
        중심 좌표 (x0, y0) 기준으로 1D 밝기 프로파일 절단법으로 FWHM 추정

        Parameters:
            image : 2D numpy array
                별이 있는 이미지
            x0, y0 : float
                별 중심의 좌표
            size : int
                자를 패치 크기 (홀수 추천)

        Returns:
            dict : {
                'fwhm_x', 'fwhm_y', 'sigma_x', 'sigma_y', 'success_x', 'success_y'
            }
        """
        half = size // 2
        h, w = image.shape
        x0, y0 = int(round(x0)), int(round(y0))

        if x0 - half < 0 or y0 - half < 0 or x0 + half >= w or y0 + half >= h:
            raise ValueError("Patch 영역이 이미지 밖으로 나갑니다.")

        patch = image[y0 - half:y0 + half + 1, x0 - half:x0 + half + 1]

        # X, Y 프로파일 추출
        profile_x = patch[half, :]  # y 방향 중앙 라인
        profile_y = patch[:, half]  # x 방향 중앙 라인
        x = np.arange(size)

        result = {}

        for direction, profile in zip(['x', 'y'], [profile_x, profile_y]):
            amp_guess = profile.max() - profile.min()
            offset_guess = profile.min()
            p0 = [amp_guess, size // 2, 3.0, offset_guess]

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    popt, _ = curve_fit(self.gaussian_1d, x, profile, p0=p0)
                    sigma = abs(popt[2])
                    fwhm = 2.3548 * sigma
                    result[f'fwhm_{direction}'] = fwhm
                    result[f'sigma_{direction}'] = sigma
                    result[f'success_{direction}'] = True
                except Exception:
                    result[f'fwhm_{direction}'] = np.nan
                    result[f'sigma_{direction}'] = np.nan
                    result[f'success_{direction}'] = False

        return result
        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
