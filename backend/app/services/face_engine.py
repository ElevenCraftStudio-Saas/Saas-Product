import insightface
from insightface.app import FaceAnalysis
import numpy as np
import cv2
import os

class FaceEngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FaceEngine, cls).__new__(cls)
            # Initialize FaceAnalysis
            # name='buffalo_l' is a common accurate model
            cls._instance.app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
            cls._instance.app.prepare(ctx_id=0, det_size=(640, 640))
        return cls._instance

    def get_faces(self, image_path):
        img = cv2.imread(image_path)
        if img is None:
            return []
        faces = self.app.get(img)
        return faces

face_engine = FaceEngine()
