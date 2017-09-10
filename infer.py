#!/usr/bin/env python3
#-------------------------------------------------------------------------------
# Author: Lukasz Janyst <lukasz@jany.st>
# Date:   09.09.2017
#-------------------------------------------------------------------------------
# This file is part of SSD-TensorFlow.
#
# SSD-TensorFlow is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SSD-TensorFlow is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SSD-Tensorflow.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------

import argparse
import pickle
import math
import sys
import cv2
import os

import tensorflow as tf
import numpy as np

from ssdvgg import SSDVGG
from utils import str2bool
from tqdm import tqdm

#-------------------------------------------------------------------------------
def sample_generator(samples, image_size, batch_size):
    image_size = (image_size.w, image_size.h)
    for offset in range(0, len(samples), batch_size):
        files = samples[offset:offset+batch_size]
        images = []
        names  = []
        for image_file in files:
            image = cv2.resize(cv2.imread(image_file), image_size)
            images.append(image.astype(np.float32))
            names.append(os.path.basename(image_file))
        yield np.array(images), names

#-------------------------------------------------------------------------------
def main():
    #---------------------------------------------------------------------------
    # Parse commandline
    #---------------------------------------------------------------------------
    parser = argparse.ArgumentParser(description='SSD inference')
    parser.add_argument("files", nargs="*")
    parser.add_argument('--name', default='test',
                        help='project name')
    parser.add_argument('--checkpoint', type=int, default=-1,
                        help='checkpoint to restore; -1 is the most recent')
    parser.add_argument('--training-data',
                        default='pascal-voc-2007/training-data.pkl',
                        help='Information about parameters used for training')
    parser.add_argument('--output-dir', default='test-output',
                        help='directory for the resulting images')
    parser.add_argument('--annotate', type=str2bool, default='False',
                        help="Annotate the date samples")
    parser.add_argument('--dump-prediction', type=str2bool, default='False',
                        help="Annotate the date samples")
    parser.add_argument('--batch-size', type=int, default=32,
                        help='batch size')
    args = parser.parse_args()

    #---------------------------------------------------------------------------
    # Check if we can get the checkpoint
    #---------------------------------------------------------------------------
    state = tf.train.get_checkpoint_state(args.name)
    if state is None:
        print('[!] No network state found in ' + args.name)
        return 1

    try:
        checkpoint_file = state.all_model_checkpoint_paths[args.checkpoint]
    except IndexError:
        print('[!] Cannot find checkpoint ' + str(args.checkpoint_file))
        return 1

    metagraph_file = checkpoint_file + '.meta'

    if not os.path.exists(metagraph_file):
        print('[!] Cannot find metagraph ' + metagraph_file)
        return 1

    #---------------------------------------------------------------------------
    # Load the training data
    #---------------------------------------------------------------------------
    try:
        with open(args.training_data, 'rb') as f:
            data = pickle.load(f)
        preset     = data['preset']
        image_size = preset.image_size
    except (FileNotFoundError, IOError, KeyError) as e:
        print('[!] Unable to load training data:', str(e))
        return 1

    #---------------------------------------------------------------------------
    # Create a list of files to analyse and make sure that the output directory
    # exists
    #---------------------------------------------------------------------------
    files = []
    if args.annotate:
        if args.files:
            files = list(filter(lambda x: os.path.exists(x), args.files))

        if not files:
            print('[!] No files specified')
            return 1

        if not os.path.exists(args.output_dir):
            os.makedirs(args.output_dir)

    #---------------------------------------------------------------------------
    # Print parameters
    #---------------------------------------------------------------------------
    print('[i] Project name:      ', args.name)
    print('[i] Network checkpoint:', checkpoint_file)
    print('[i] Metagraph file:    ', metagraph_file)
    print('[i] Training data:     ', args.training_data)
    print('[i] Image size:        ', image_size)
    print('[i] Number of files:   ', len(files))
    print('[i] Batch size:        ', args.batch_size)

    #---------------------------------------------------------------------------
    # Create the network
    #---------------------------------------------------------------------------
    with tf.Session() as sess:
        print('[i] Creating the model...')
        net = SSDVGG(sess)
        net.build_from_metagraph(metagraph_file, checkpoint_file)

        #-----------------------------------------------------------------------
        # Process the images
        #-----------------------------------------------------------------------
        generator = sample_generator(files, image_size, args.batch_size)
        n_sample_batches = int(math.ceil(len(files)/args.batch_size))
        description = '[i] Processing samples'

        for x, names in tqdm(generator, total=n_sample_batches,
                      desc=description, unit='batches'):
            feed = {net.image_input:  x,
                    net.keep_prob:    1}
            boxes = sess.run(net.result, feed_dict=feed)

            #-------------------------------------------------------------------
            # Dump the prediction
            #-------------------------------------------------------------------
            if args.annotate and args.dump_prediction:
                for i in range(len(names)):
                    fn = args.output_dir+'/'+names[i]+'.npy'
                    np.save(fn, boxes[i])

    print('[i] All done.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
