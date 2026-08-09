# OCR model assets

The ground station uses the OpenCV Zoo OCR pipeline locally on Windows:

- `text_detection_cn_ppocrv3_2023may.onnx`: PP-OCRv3 Chinese text detector.
- `text_recognition_CRNN_CN_2021nov.onnx`: CRNN Chinese text recognizer.
- `charset_3944_CN.txt`: character set paired with the CRNN model.

Sources:

- https://github.com/opencv/opencv_zoo/tree/main/models/text_detection_ppocr
- https://github.com/opencv/opencv_zoo/tree/main/models/text_recognition_crnn

The files are distributed by OpenCV Zoo under the Apache License 2.0.
