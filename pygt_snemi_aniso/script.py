from __future__ import print_function
import h5py
import numpy as np
from numpy import float32, int32, uint8, dtype
import sys

# Relative path to where PyGreentea resides
pygt_path = '../../PyGreentea'


import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), pygt_path))

# Other python modules
import math

# Load PyGreentea
import PyGreentea as pygt

# Create the network we want
class NetConf:
    # 10 GB total memory limit
    mem_global_limit = 10 * 1024 * 1024 * 1024
    # 4 GB single buffer memory limit
    mem_buf_limit = 4 * 1024 * 1024 * 1024
    # Desired input dimensions (will select closest possible)
    input_shape = [44,132,132]
    # Desired output dimensions (will select closest posisble)
    output_shape = [16, 44, 44]
    # Number of U-Net Pooling-Convolution downsampling/upsampling steps
    unet_depth = 3
    # Number of feature maps in the start
    fmap_start = 64
    # Number of input feature maps
    fmap_input = 1
    # Number of ouput feature maps
    fmap_output = 11
    # Feature map increase rule (downsampling)
    def unet_fmap_inc_rule(self, fmaps):
        return int(math.ceil(fmaps * 3));
    # Feature map decrease rule (upsampling)
    def unet_fmap_dec_rule(self, fmaps):
        return int(math.ceil(fmaps / 3));
    # Skewed U-Net downsampling strategy
    unet_downsampling_strategy = [[1,2,2],[1,2,2],[1,2,2]]
    # Number of SK-Net Pooling-Convolution steps
    sknet_conv_depth = 0
    # Feature map increase rule
    def sknet_fmap_inc_rule(self, fmaps):
        return int(math.ceil(fmaps * 1.5));
    # Number of 1x1 (IP) Convolution steps
    sknet_ip_depth = 0
    # Feature map increase rule from SK-Convolution to IP
    def sknet_fmap_bridge_rule(self, fmaps):
        return int(math.ceil(fmaps * 4));
    # Feature map decrease rule within IP
    def sknet_fmap_dec_rule(self, fmaps):
        return int(math.ceil(fmaps / 2.5));
    # Loss function and mode ("malis", "euclid", "softmax")
    loss_function = "euclid"


netconf = NetConf()
netconf.loss_function = "euclid"
train_net_conf_euclid, test_net_conf = pygt.netgen.create_nets(netconf)
netconf.loss_function = "malis"
train_net_conf_malis, test_net_conf = pygt.netgen.create_nets(netconf)

with open('net_train_euclid.prototxt', 'w') as f:
    print(train_net_conf_euclid, file=f)
with open('net_train_malis.prototxt', 'w') as f:
    print(train_net_conf_malis, file=f)
with open('net_test.prototxt', 'w') as f:
    print(test_net_conf, file=f)

# Load the datasets
hdf5_raw_file = '/groups/turaga/home/turagas/data/SNEMI3D/train/raw.hdf5'
hdf5_gt_file = '/groups/turaga/home/turagas/data/SNEMI3D/train/labels_id.hdf5'
hdf5_aff_file = '/groups/turaga/home/turagas/data/SNEMI3D/train/labels_aff11.hdf5'

hdf5_raw = h5py.File(hdf5_raw_file, 'r')
hdf5_gt = h5py.File(hdf5_gt_file, 'r')
hdf5_aff = h5py.File(hdf5_aff_file, 'r')
hdf5_raw_ds =pygt.normalize(np.asarray(hdf5_raw[hdf5_raw.keys()[0]]).astype(float32), -1, 1)
hdf5_gt_ds = np.asarray(hdf5_gt[hdf5_gt.keys()[0]]).astype(float32)
hdf5_aff_ds = np.asarray(hdf5_aff[hdf5_aff.keys()[0]]).astype(float32)

dataset = {}
dataset['data'] = hdf5_raw_ds[None, :]
dataset['label'] = hdf5_aff_ds;
dataset['components'] = hdf5_gt_ds[None, :]
dataset['nhood'] = pygt.malis.mknhood3d_aniso()

test_dataset = {}
test_dataset['data'] = hdf5_raw_ds
test_dataset['label'] = hdf5_aff_ds


# Set train options
class TrainOptions:
    loss_function = "euclid"
    loss_output_file = "log/loss.log"
    test_output_file = "log/test.log"
    test_interval = 4000
    scale_error = True
    training_method = "affinity"
    recompute_affinity = True
    train_device = 0
    test_device = 2
    test_net='net_test.prototxt'


options = TrainOptions()

# Set solver options
solver_config = pygt.caffe.SolverParameter()
solver_config.train_net = 'net_train_euclid.prototxt'
solver_config.base_lr = 0.00001
solver_config.momentum = 0.99
solver_config.weigth_decay = 0.000005
solver_config.lr_policy = 'inv'
solver_config.gamma = 0.0001
solver_config.power = 0.75
solver_config.max_iter = 8000
solver_config.snapshot = 2000
solver_config.snapshot_prefix = 'net'
solver_config.display = 1

# Set devices
# pygt.caffe.enumerate_devices(False)
pygt.caffe.set_devices((options.train_device, options.test_device))


solverstates = pygt.getSolverStates(solver_config.snapshot_prefix);

# First training method
if (len(solverstates) == 0 or solverstates[-1][0] < solver_config.max_iter):
    solver, test_net = pygt.init_solver(solver_config, options)
    if (len(solverstates) > 0):
        solver.restore(solverstates[-1][1])
    pygt.train(solver, test_net, [dataset], [test_dataset], options)


solverstates = pygt.getSolverStates(solver_config.snapshot_prefix);

# Second training method
if (solverstates[-1][0] >= solver_config.max_iter):
    # Modify some solver options
    solver_config.max_iter = 16000
    solver_config.train_net = 'net_train_malis.prototxt'
    options.loss_function = 'malis'
    # Initialize and restore solver
    solver, test_net = pygt.init_solver(solver_config, options)
    if (len(solverstates) > 0):
        solver.restore(solverstates[-1][1])
    pygt.train(solver, test_net, [dataset], [test_dataset], options)
    





