#%% This example shows how to train FBPConvNet for full angle, noisy measurements.

#%% Imports
import matplotlib.pyplot as plt
import numpy as np
import torch
from torch.utils.data import DataLoader
from tqdm import tqdm
import pathlib
import LION.CTtools.ct_geometry as ctgeo
import LION.CTtools.ct_utils as ct
from LION.data_loaders.LIDC_IDRI import LIDC_IDRI
from LION.models.LPD import LPD
from LION.utils.parameter import Parameter
from ts_algorithms import fdk


import LION.experiments.ct_experiments as ct_experiments


#%%
# % Chose device:
device = torch.device("cuda:0")
torch.cuda.set_device(device)
# Define your data paths
savefolder = pathlib.Path("/store/DAMTP/ab2860/trained_models/test_debbuging/")
datafolder = pathlib.Path(
    "/store/DAMTP/ab2860/AItomotools/data/AItomotools/processed/LIDC-IDRI/"
)
final_result_fname = savefolder.joinpath("LPD_final_iter.pt")
checkpoint_fname = savefolder.joinpath("LPD_check_*.pt")
validation_fname = savefolder.joinpath("LPD_min_val.pt")
#
#%% Define experiment

experiment = ct_experiments.LowDoseCTRecon(datafolder=datafolder)

#%% Dataset
lidc_dataset = experiment.get_training_dataset()
lidc_dataset_val = experiment.get_validation_dataset()

#%% Define DataLoader
# Use the same amount of training
batch_size = 1
lidc_dataloader = DataLoader(lidc_dataset, batch_size, shuffle=True)
lidc_validation = DataLoader(lidc_dataset_val, batch_size, shuffle=True)

#%% Model
# Default model is already from the paper.
default_parameters = LPD.default_parameters()
# This makes the LPD calculate the step size for the backprojection, which in my experience results in much much better pefromace
# as its all in the correct scale.
default_parameters.learned_step = True
default_parameters.step_positive = True
default_parameters.n_iters = 5
model = LPD(experiment.geo, default_parameters).to(device)


#%% Optimizer
train_param = Parameter()

# loss fn
loss_fcn = torch.nn.MSELoss()
train_param.optimiser = "adam"

# optimizer
train_param.epochs = 100
train_param.learning_rate = 1e-3
train_param.betas = (0.9, 0.99)
train_param.loss = "MSELoss"
optimiser = torch.optim.Adam(
    model.parameters(), lr=train_param.learning_rate, betas=train_param.betas
)

# learning parameter update
steps = len(lidc_dataloader)

model.train()
min_valid_loss = np.inf
total_loss = np.zeros(train_param.epochs)
start_epoch = 0

# %% Check if there is a checkpoint saved, and if so, start from there.

# If there is a file with the final results, don't run again
if model.final_file_exists(savefolder.joinpath(final_result_fname)):
    print("final model exists! You already reahced final iter")
    exit()

model, optimiser, start_epoch, total_loss, _ = LPD.load_checkpoint_if_exists(
    checkpoint_fname, model, optimiser, total_loss
)
print(f"Starting iteration at epoch {start_epoch}")

#%% train
for epoch in range(start_epoch, train_param.epochs):
    train_loss = 0.0
    for index, (sinogram, target_reconstruction) in tqdm(enumerate(lidc_dataloader)):

        optimiser.zero_grad()
        reconstruction = model(sinogram)
        loss = loss_fcn(reconstruction, target_reconstruction)

        loss.backward()

        train_loss += loss.item()

        optimiser.step()

        bad_recon = fdk(model.op, sinogram[0])
        if index == 0:
            plt.figure()
            plt.subplot(1, 3, 1)
            plt.imshow(reconstruction[0, 0, :, :].cpu().detach().numpy())
            plt.clim(0, 3)
            plt.subplot(1, 3, 2)
            plt.imshow(target_reconstruction[0, 0, :, :].cpu().detach().numpy())
            plt.clim(0, 3)
            plt.subplot(1, 3, 3)
            plt.imshow(bad_recon[0, :, :].cpu().detach().numpy())
            plt.clim(0, 3)
            plt.savefig("recon.png")
            plt.close()
    total_loss[epoch] = train_loss
    # Validation
    valid_loss = 0.0
    model.eval()
    for index, (sinogram, target_reconstruction) in tqdm(enumerate(lidc_validation)):

        reconstruction = model(sinogram)
        loss = loss_fcn(target_reconstruction, reconstruction)
        valid_loss += loss.item()

    print(
        f"Epoch {epoch+1} \t\t Training Loss: {train_loss / len(lidc_dataloader)} \t\t Validation Loss: {valid_loss / len(lidc_validation)}"
    )

    if min_valid_loss > valid_loss:
        print(
            f"Validation Loss Decreased({min_valid_loss:.6f}--->{valid_loss:.6f}) \t Saving The Model"
        )
        min_valid_loss = valid_loss
        # Saving State Dict
        model.save(
            validation_fname,
            epoch=epoch + 1,
            training=train_param,
            loss=min_valid_loss,
            dataset=experiment.param,
        )

    # Checkpoint every 10 iters anyway
    if epoch % 10 == 0:
        model.save_checkpoint(
            pathlib.Path(str(checkpoint_fname).replace("*", f"{epoch+1:04d}")),
            epoch + 1,
            total_loss,
            optimiser,
            train_param,
            dataset=experiment.param,
        )


plt.figure()
plt.plot(total_loss[1:])
plt.savefig("loss.png")

model.save(
    final_result_fname,
    epoch=train_param.epochs,
    training=train_param,
    dataset=experiment.param,
)
