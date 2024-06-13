import torch
from torch import nn
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from utils.evaluation import calc_crps, plot_trues_preds, plot_distibuation, metric
from data.data import data_prep
from benchmarks.forGAN import Generator, Discriminator

device = torch.device("cuda:0") if torch.cuda.is_available() else torch.device("cpu")

torch.manual_seed(42)
rs = np.random.RandomState(1234)


def load_real_samples(batch_size):
    idx = rs.choice(x_train.shape[0], batch_size)
    x_batch = x_train[idx]
    y_batch = y_train[idx]
    # print("loading real samples")
    # print("x_batch shape: ", x_batch.shape)
    # print("y_batch shape", y_batch.shape)
    # lables = ones((batch_size, 1))  #Labels=1 indicating they are real
    return x_batch, y_batch

def generate_fake_samples(generator, noise_size, x_batch):
        # generate points in latent space

        noise_batch = torch.tensor(rs.normal(0, 1, (x_batch.size(0), noise_size)),
                                   device=device, dtype=torch.float32)

        # print("noise_batch shape", noise_batch.shape)

        y_fake = generator(noise_batch, x_batch).detach()
        # labels = zeros((x_batch.size(0), 1))  #Label=0 indicating they are fake
        return x_batch, y_fake
def train(best_crps):
    print("epochs", epochs)

    for step in range(epochs):

        d_loss = 0

        # load real samples
        # x_bach = batch x seq_len x feature_no [16, 10, 2]
        # y_batch = batch_size x pred_len  [16, 1]
        x_batch, y_batch = load_real_samples(batch_size)

        # train D on real samples
        discriminator.zero_grad()
        d_real_decision = discriminator(y_batch, x_batch)
        d_real_loss = adversarial_loss(d_real_decision,
                                       torch.full_like(d_real_decision, 1, device=device))
        d_real_loss.backward()
        d_loss += d_real_loss.detach().cpu().numpy()

        # train discriminator on fake data
        x_batch, y_fake = generate_fake_samples(generator, noise_size, x_batch)
        d_fake_decision = discriminator(y_fake, x_batch)
        d_fake_loss = adversarial_loss(d_fake_decision,
                                       torch.full_like(d_fake_decision, 0, device=device))
        d_fake_loss.backward()

        optimizer_d.step()
        d_loss += d_fake_loss.detach().cpu().numpy()

        d_loss = d_loss / 2

        generator.zero_grad()
        noise_batch = torch.tensor(rs.normal(0, 1, (batch_size, noise_size)), device=device,
                                   dtype=torch.float32)
        y_fake = generator(noise_batch, x_batch)

        # print("y_fake", y_fake.shape)
        d_g_decision = discriminator(y_fake, x_batch)
        g_loss = -1 * adversarial_loss(d_g_decision, torch.full_like(d_g_decision, 0, device=device))

        g_loss.backward()
        optimizer_g.step()

        g_loss = g_loss.detach().cpu().numpy()

        # Validation
        if step % 100 == 0:
            with torch.no_grad():
                generator.eval()

                predictions = []
                for _ in range(200):
                    noise_batch = torch.tensor(rs.normal(0, 1, (x_val.size(0), noise_size)),
                                               device=device,
                                               dtype=torch.float32)
                    predictions.append(generator(noise_batch, x_val).cpu().detach().numpy())

                predictions = np.stack(predictions)

                generator.train()
            # print(y_val.shape)
            crps = calc_crps(y_val, predictions[:100], predictions[100:])

            if crps <= best_crps:
                best_crps = crps
                torch.save({'g_state_dict': generator.state_dict()},
                           "./results/forGAN/best.torch")

            print("step : {} , d_loss : {} , g_loss : {}, crps : {}, best crps : {}".format(step, d_loss, g_loss, crps,
                                                                                            best_crps))



if __name__ == '__main__':
    df = pd.read_csv('dataset/oil.csv')
    df = df[6:]
    df = df[['Price', 'SENT']]

    seq_len, pred_len, feature_no = 5, 1, len(df.columns)

    hidden_dim = 4
    noise_dim = 32
    dim = 128
    train_size, valid_size, test_size = 2000, 180, 200
    data = data_prep(df, seq_len, pred_len, train_size, valid_size, test_size)
    print(data['X_test'].shape)
    print(data['y_test'].shape)

    epochs = 10000
    batch_size = 16
    noise_size = 32
    x_batch_size = data['X_train'].shape[1]  # 24 sequence length
    print(x_batch_size)
    generator_latent_size = 4  # hidden layer
    discriminator_latent_size = 64

    generator = Generator(noise_size=noise_size,
                          x_batch_size=x_batch_size,
                          generator_latent_size=generator_latent_size, feature_no=feature_no).to(device)

    discriminator = Discriminator(x_batch_size=x_batch_size,
                                  discriminator_latent_size=discriminator_latent_size).to(device)

    print(generator)
    print(discriminator)

    x_train = torch.tensor(data['X_train'], device=device, dtype=torch.float32)
    y_train = torch.tensor(data['y_train'], device=device, dtype=torch.float32)
    x_val = torch.tensor(data['X_valid'], device=device, dtype=torch.float32)
    y_val = data['y_valid']

    optimizer_g = torch.optim.RMSprop(generator.parameters())
    optimizer_d = torch.optim.RMSprop(discriminator.parameters())
    adversarial_loss = nn.BCELoss()
    adversarial_loss = adversarial_loss.to(device)

    best_crps = np.inf

    is_train = True

    if is_train:
        train(best_crps)
    else:
        print('training mode is off')






    #print(predictions.shape)
    checkpoint = torch.load("./results/forGAN/best.torch")
    generator.load_state_dict(checkpoint['g_state_dict'])

    x_test = torch.tensor(data['X_test'], device=device, dtype=torch.float32)
    predictions = []

    with torch.no_grad():
                    generator.eval()
                    noise_batch = torch.tensor(rs.normal(0, 1, (x_test.size(0), noise_size)), device=device,
                                               dtype=torch.float32)
                    predictions.append(generator(noise_batch, x_test).detach().cpu().numpy().flatten())

    predictions = np.stack(predictions).flatten()
    print("preds", predictions.shape)

    y_test = data['y_test'].flatten()
    print("trues and preds", y_test.shape, predictions.shape)


    



    trues = data['y_test'].flatten()
    preds = predictions.flatten()
    plot_distibuation(trues, preds)
    plot_trues_preds(trues, preds)

    metrics = metric(trues, preds)




