#%% Noise2Inverse train

#%% Imports

# Basic science imports
import matplotlib.pyplot as plt
import numpy as np
import torch
from torch.utils.data import DataLoader

# basic python imports
from tqdm import tqdm
import pathlib
import copy

# LION imports
import LION.CTtools.ct_utils as ct
from LION.models.FBPConvNet import FBPConvNet
from LION.utils.parameter import Parameter
import LION.experiments.ct_experiments as ct_experiments
from ts_algorithms import fdk


#%%
# % Chose device:
device = torch.device("cuda:0")
torch.cuda.set_device(device)
# Define your data paths
savefolder = pathlib.Path("/store/DAMTP/ab2860/low_dose/")
datafolder = pathlib.Path(
    "/store/DAMTP/ab2860/AItomotools/data/AItomotools/processed/LIDC-IDRI/"
)
final_result_fname = savefolder.joinpath("FBConvNet_final_iter.pt")
checkpoint_fname = savefolder.joinpath("FBConvNet_check_*.pt")
#
#%% Define experiment
experiment = ct_experiments.LowDoseCTRecon(datafolder=datafolder)

#%% Dataset
dataset = experiment.get_testing_dataset()
batch_size = 1
dataloader = DataLoader(dataset, batch_size, shuffle=True)

#%% Load model
fbpconv_model, fbpconv_param, fbpconv_data = FBPConvNet.load(final_result_fname)
fbpconv_model.eval()

# loop trhough testing data
for index, (sinogram, target_reconstruction) in tqdm(enumerate(dataloader)):

    # This is FDK for comparison
    bad_recon = torch.zeros(target_reconstruction.shape, device=device)
    for sino in range(sinogram.shape[0]):
        bad_recon[sino] = fdk(dataset.operator, sinogram[sino])
    fbpconvnet_out = fbpconv_model(bad_recon)

    # do whatever you want with this.
