# pylint: skip-file
import os
import sys
import numpy as np
import scipy.ndimage
from time import time

sys.path.append("../..")
from dataset import Dataset, ImagesBatch

if __name__ == "__main__":
    # number of items in the dataset
    K = 1000
    S = 128

    # Fill-in dataset with sample data
    def gen_data(num_items, shape):
        index = np.arange(num_items)
        data = np.random.randint(0, 255, size=num_items * shape[0] * shape[1])
        data = data.reshape(num_items, shape[0], shape[1]).astype('uint8')
        ds = Dataset(index=index, batch_class=ImagesBatch)
        return ds, data


    # Create a dataset
    print("Generating...")
    dataset, images = gen_data(K, (S, S))

    pipeline = (dataset.p
                .load((images,))
                .convert_to_pil()
                .resize(shape=(384, 384))
                .random_rotate(angle=(-np.pi/4, np.pi/4), preserve_shape=True)
                .convert_from_pil()
                .apply_transform('images', 'images', scipy.ndimage.filters.gaussian_filter, sigma=3)
                .crop(shape=(256, 256))
    )

    print("Start...")
    t = time()
    pipeline.run(K//10, n_epochs=1, prefetch=5, target='mpc')
    print("End", time() - t)
