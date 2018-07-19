"""Train the embedder
"""
import logging
import os
import random

import torch
import torch.multiprocessing as mp

import cv2


def loss_fn(anchor_emb, positive_emb, negative_emb, alpha=0.2):
    batch_size = anchor_emb.shape[0]
    loss = (torch.norm(anchor_emb - positive_emb)**2 -
            torch.norm(anchor_emb - negative_emb)**2) / batch_size + alpha
    return loss


class DataGenerator:
    def __init__(self, data_dir, batch_size, logger):
        self.data_dir = data_dir
        self.face_images = []
        if not os.path.exists(data_dir):
            logger.error('Data dir %s doesn\'t exist' % data_dir)
            return
        people = os.listdir(data_dir)
        for person in people:
            person_dir = os.path.join(data_dir, person)
            faces = os.listdir(person_dir)
            if len(faces) > 0:
                face_images = list(
                    map(lambda img_name: os.path.join(person_dir, img_name),
                        faces))
                self.face_images.append(face_images)
        self.batch_size = batch_size
        self.logger = logger
        self.person_idx = 0
        self.image_idx = 0

    def __iter__(self):
        return self

    def __next__(self):
        anchors = []
        positives = []
        negatives = []

        batch_counter = 0
        while (batch_counter < self.batch_size) and len(self.face_images) > 1:
            if self.person_idx == 0:
                random.shuffle(self.face_images)
                self.person_idx += 1
            if self.image_idx == 0:
                random.shuffle(self.face_images[self.person_idx])
                self.image_idx = 1

            if len(self.face_images[self.person_idx]) > 1:
                anchors.append(
                    cv2.imread(
                        self.face_images[self.person_idx][self.image_idx]))
                positives.append(
                    cv2.imread(
                        self.face_images[self.person_idx][self.image_idx - 1]))
                negative_idx = random.randint(
                    0,
                    len(self.face_images[self.person_idx - 1]) - 1)
                negatives.append(
                    cv2.imread(
                        self.face_images[self.person_idx - 1][negative_idx]))
                batch_counter += 1

            self.image_idx += 1
            if self.image_idx >= len(self.face_images[self.person_idx]):
                self.image_idx = 0
                self.person_idx += 1
                self.person_idx %= len(self.face_images)

        anchors = torch.Tensor(anchors)
        positives = torch.Tensor(positives)
        negatives = torch.Tensor(negatives)
        batch = torch.cat((anchors, positives, negatives), dim=0)
        batch = torch.transpose(batch, 1, 3)
        batch = torch.transpose(batch, 2, 3)
        return batch


class LoadingWorker(mp.Process):
    def __init__(self, data_dir, batch_size, queue):
        super().__init__()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.generator = DataGenerator(data_dir, batch_size, self.logger)
        self.queue = queue
        self.exit = mp.Event()

    def run(self):
        while not self.exit.is_set():
            self.logger.info('loading...')
            batch = self.generator.__next__()
            self.queue.put(batch)

    def terminate(self):
        self.logger.info('Shutting down loader')
        self.exit.set()
        while not self.queue.empty():
            self.queue.get()

import time

queue = mp.Queue(10)
process = LoadingWorker('data/processed', 10, queue)
process.start()
time.sleep(5)
print(queue.qsize())
print(queue.get().shape)
process.terminate()
process.join()