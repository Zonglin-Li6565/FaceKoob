"""The server for running face embeddings
"""
import argparse
import logging
import socket
import ssl
from threading import Thread

import numpy as np

import dlib

from numpy_socket import NumpySocket


class EmbeddingServer:
    def __init__(self,
                 predictor_path,
                 model_path,
                 cert_path,
                 key_path,
                 logger,
                 image_shape,
                 hostname='',
                 port=12220):
        self.socket = socket.socket()
        self.socket.bind((hostname, port))
        self.logger = logger
        self.predictor = dlib.shape_predictor(predictor_path)
        self.model = dlib.face_recognition_model_v1(model_path)
        self.running = False
        self.cert_path = cert_path
        self.key_path = key_path
        self.image_shape = image_shape

    def handle_one_client(self, socket, client_addr):
        numpy_socket = NumpySocket(socket)
        while True:
            image = numpy_socket.receive_numpy()
            if image is None:
                self.logger.info('Client %s disconnected' % client_addr)
                break
            if image.shape != self.image_shape:
                self.logger.error(
                    'Received image with shape %s from %s, expected shape %s' %
                    (image.shape, client_addr, self.image_shape))
                break
            bounding_box = dlib.rectangle(0, 0, image.shape[1], image.shape[0])
            landmarks = self.predictor(image, bounding_box)
            embedding = self.model(image, landmarks)
            numpy_socket.send_numpy(embedding)

    def run(self):
        self.socket.listen(5)
        self.running = True
        while self.running:
            client_socket, client_addr = self.socket.accept()
            self.logger.info('Connection from client: %s' % client_addr)
            ssl_socket = ssl.wrap_socket(
                client_socket,
                server_side=True,
                certfile=self.cert_path,
                keyfile=self.key_path)
            thread = Thread(
                target=self.handle_one_client, args=(ssl_socket, client_addr))
            thread.start()
