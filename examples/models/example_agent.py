from perturbationdrive import ADS

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.models import load_model
from typing import List, Any
from numpy import dtype, ndarray, uint8
import numpy as np
import os


class ExampleAgent(ADS):
    """
    Example agent using Dave2 architecture trained on SDSandBox Sim Data
    """

    def __init__(self):
        if not (
            os.path.exists("./examples/models/generatedRoadModel.h5")
            and os.path.isfile("./examples/models/generatedRoadModel.h5")
        ):
            print(f"{5 * '+'} Warning: ADS file does not exists {5 * '+'}")
        self.model = load_model(
            "./examples/models/generatedRoadModel.h5", compile=False
        )
        self.model.compile(loss="sgd", metrics=["mse"])

    def action(self, input: ndarray[Any, dtype[uint8]]) -> List:
        """
        Takes one action step given the input, here the input is a cv2 image.
        This method also contains the preparation for the underlying model
        """
        # adapt dtype of input
        img_arr = np.asarray(input, dtype=np.float32)
        # add batch dimension
        img_arr = img_arr.reshape((1,) + img_arr.shape)
        return self.model(img_arr, training=False)
