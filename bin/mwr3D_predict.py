#!/usr/bin/env python3
import keras
import numpy as np
import os
import logging

from mwr.preprocessing.simulate import apply_wedge
from mwr.util.norm import normalize
from mwr.util.toTile import reform3D
import mrcfile
from mwr.util.image import *


# def wedge_imposing(data):
#     #data are in 4 dimensions:(n,cropsize,cropsize,cropsize,1)
#     dim = data.shape
#     cubes=np.ones(dim)
#     for i in range(dim[0]):
#         print('**%d',i)
#         one_cube=data[i,:,:,:,0]
#         cubes[i,:,:,:,0]=apply_wedge1(one_cube)
#     return cubes
    
def str2bool(v):
    if isinstance(v, bool):
       return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


def predict(args):

    logging.basicConfig(format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d:%H:%M:%S')
    if args.log_level == "debug":
        logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    # import argparse
    # parser = argparse.ArgumentParser(description='Process some integers.')
    # parser.add_argument('mrc_file', type=str, default=None, help='Your mrc file')
    # parser.add_argument('output_file', type=str, default=None, help='output mrc file')
    # parser.add_argument('--weight', type=str, default='results/modellast.h5' ,help='Weight file name to save')
    # parser.add_argument('--model', type=str, default='model.json' ,help='Data file name to save')
    # parser.add_argument('--gpuID', type=str, default='0,1,2,3', help='number of gpu for training')
    # parser.add_argument('--cubesize', type=int, default=64, help='size of cube')
    # parser.add_argument('--cropsize', type=int, default=96, help='crop size larger than cube for overlapping tile')
    # parser.add_argument('--batchsize', type=int, default=8, help='batch size')
    # parser.add_argument('--norm', type=str, default='True', help='bool; default: percentile normlization')
    # args = parser.parse_args()
    if_percentile = str2bool(args.norm)
    os.environ["CUDA_DEVICE_ORDER"]="PCI_BUS_ID"
    os.environ["CUDA_VISIBLE_DEVICES"]=args.gpuID 
    logger.info('percentile:{}'.format(if_percentile))

    ngpus = len(args.gpuID.split(','))
    from keras.models import model_from_json
    json_file = open(args.model, 'r')
    loaded_model_json = json_file.read()
    json_file.close()
    model = model_from_json(loaded_model_json)
    logger.info('gpuID:{}'.format(args.gpuID))
    if ngpus >1:
        from keras.utils import multi_gpu_model
        model = multi_gpu_model(model, gpus=ngpus, cpu_merge=True, cpu_relocation=False)
    model.load_weights(args.weight)

    logger.info("Loaded model from disk")

    N = args.batchsize * ngpus
    root_name = args.mrc_file.split('/')[-1].split('.')[0]
    print('predicting:{}'.format(root_name))
    with mrcfile.open(args.mrc_file) as mrcData:
        real_data = mrcData.data.astype(np.float32)*-1
    real_data = normalize(real_data,percentile=if_percentile)
    data=np.expand_dims(real_data,axis=-1)
    reform_ins = reform3D(data)
    data = reform_ins.pad_and_crop_new(args.cubesize,args.cropsize)
    #to_predict_data_shape:(n,cropsize,cropsize,cropsize,1)
    #imposing wedge to every cubes
    #data=wedge_imposing(data)

    num_batches = data.shape[0]
    if num_batches%N == 0:
        append_number = 0
    else:
        append_number = N - num_batches%N
    data = np.append(data, data[0:append_number], axis = 0)

    outData=model.predict(data, batch_size= args.batchsize,verbose=1)

    outData = outData[0:num_batches]
    outData=reform_ins.restore_from_cubes_new(outData.reshape(outData.shape[0:-1]), args.cubesize, args.cropsize)

    outData = normalize(outData,percentile=if_percentile)
    with mrcfile.new(args.output_file, overwrite=True) as output_mrc:
        output_mrc.set_data(-outData)
    print('Done predicting')
    # predict(args.model,args.weight,args.mrc_file,args.output_file, cubesize=args.cubesize, cropsize=args.cropsize, batchsize=args.batchsize, gpuID=args.gpuID, if_percentile=if_percentile)