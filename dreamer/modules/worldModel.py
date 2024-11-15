import torch
import torch.nn as nn
import torch.nn.functional as F
import os
import random
from dreamer.modules.rssm import RSSM
from dreamer.modules.decoder import Decoder
from dreamer.modules.rewardModel import RewardPredictor
from dreamer.modules.continueModel import ContinuousPredictor
import torch.optim as optim

class WorldModel(nn.Module):
    def __init__(self, config) -> None:
        super(WorldModel, self).__init__()

        self.config = config
        self.rssm = RSSM(config)
        self.decoder = Decoder(config)
        self.reward_predictor = RewardPredictor(config)
        self.continue_predictor = ContinuousPredictor(config)



    def forward(self, obs, hidden_state, action):
        z_prior, z_posterior, h, dist, dynamic_dist = self.rssm(obs, hidden_state, action)   #Dynamics Predictor: Provides the prior distribution

        reconstructed_obs = self.decoder(z_posterior, h)
        reward = self.reward_predictor(z_posterior, h)
        continue_prob = self.continue_predictor(z_posterior, h)

        return {
            'prior_dist': dynamic_dist,
            'posterior_dist': dist,
            'reconstructed_obs': reconstructed_obs,
            'reward': reward,
            'continue_prob': continue_prob,
            'hidden_state': h
        }
    

    def save_world_model(self):
        self.rssm.save_rssm()
        self.reward_predictor.save()
        self.continue_predictor.save()
        self.decoder.save()
        print(f"World Model saved at {self.config.path}")

    def load_world_model(self):
        self.rssm.load_rssm()
        self.reward_predictor.load()
        self.continue_predictor.load()
        self.decoder.load()
        print(f"World model loaded at {self.config.path}")
    


class Trainer:
    def __init__(self, config, model:WorldModel) -> None:
        self.config = config
        self.model = model

        self.model.to(self.config.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=config.learning_rate)

    
    def train(self, data_loader):
        for obs, actions, rewards, dones, next_obs in data_loader:  # Assume batched data from replay buffer
            obs, actions, rewards, dones, next_obs = obs.to(self.config.device), actions.to(self.config.device), rewards.to(self.config.device), dones.to(self.config.device), next_obs.to(self.config.device)
        
            hidden_state, action = self.model.rssm.recurrent_model_input_init()

            outputs = self.model(obs, hidden_state, action)
            hidden_state = outputs['h']

            # Calculate Posterior (using next_obs with Encoder)
            z_posterior, posterior_dist = self.model.e_model(torch.cat((next_obs, hidden_state), dim=-1))

            # Calculate losses
            # Reconstruction Loss for Decoder
            reconstructed_obs = outputs['reconstructed_obs']
            recon_loss = F.mse_loss(reconstructed_obs, obs)

            # Reward Predictor Loss
            reward_pred = outputs['reward']
            reward_loss = F.mse_loss(reward_pred, rewards)

            # Continue Predictor Loss (Binary Cross-Entropy)
            continue_pred = outputs['continue_prob']
            continue_loss = F.binary_cross_entropy_with_logits(continue_pred, dones.float())

            # KL Divergence Loss
            #posterior_dist = outputs['posterior_dist']
            prior_dist = outputs['prior_dist']
            kl_div = torch.distributions.kl_divergence(posterior_dist, prior_dist).mean()
            
            # Apply free bits by clipping the KL divergence
            kl_div = torch.clamp(kl_div, min=self.config.free_bits_threshold)

            # Total Loss
            total_loss = recon_loss + reward_loss + continue_loss + self.config.kl_weight * kl_div
            
            # Backpropagation
            self.optimizer.zero_grad()
            total_loss.backward()
            self.optimizer.step()


            print(f"Total Loss: {total_loss.item()}, Recon Loss: {recon_loss.item()}, Reward Loss: {reward_loss.item()}, Continue Loss: {continue_loss.item()}, KL Loss: {kl_div.item()}")

    
    def evaluate(self, data_loader):
        self.model.eval()

        total_recon_loss = 0
        total_reward_loss = 0
        total_continue_loss = 0
        total_kl_div = 0
        num_batches = 0

        with torch.no_grad():  # Disable gradient computation
            for obs, actions, rewards, dones, next_obs in data_loader:
                # Move data to the appropriate device
                obs, actions, rewards, dones = obs.to(self.config.device), actions.to(self.config.device), rewards.to(self.config.device), dones.to(self.config.device)
                next_obs = next_obs.to(self.config.device)

                # Initialize hidden state and action at t=0
                hidden_state, action = self.model.rssm.recurrent_model_input_init()

                # Forward pass through the world model
                outputs = self.model(obs, hidden_state, action)
                hidden_state = outputs['h']

                # Calculate Posterior (using next_obs with Encoder)
                z_posterior, posterior_dist = self.model.e_model(torch.cat((next_obs, hidden_state), dim=-1))

                # Reconstruction Loss (Decoder)
                reconstructed_obs = outputs['reconstructed_obs']
                recon_loss = F.mse_loss(reconstructed_obs, obs, reduction='sum')
                total_recon_loss += recon_loss.item()

                # Reward Prediction Loss (MSE)
                reward_pred = outputs['reward']
                reward_loss = F.mse_loss(reward_pred, rewards, reduction='sum')
                total_reward_loss += reward_loss.item()

                # Continue Predictor Loss (Binary Cross-Entropy)
                continue_pred = outputs['continue_prob']
                continue_loss = F.binary_cross_entropy_with_logits(continue_pred, dones.float(), reduction='sum')
                total_continue_loss += continue_loss.item()

                # KL Divergence Loss
                #posterior_dist = outputs['posterior_dist']
                prior_dist = outputs['prior_dist']
                kl_div = torch.distributions.kl_divergence(posterior_dist, prior_dist).mean()
                total_kl_div += kl_div.item()

                # Increment the batch counter
                num_batches += 1

        # Calculate average metrics
        avg_recon_loss = total_recon_loss / len(data_loader.dataset)
        avg_reward_loss = total_reward_loss / len(data_loader.dataset)
        avg_continue_loss = total_continue_loss / len(data_loader.dataset)
        avg_kl_div = total_kl_div / num_batches

        # Print or log metrics
        print(f"Evaluation - Recon Loss: {avg_recon_loss:.4f}, Reward Loss: {avg_reward_loss:.4f}, Continue Loss: {avg_continue_loss:.4f}, KL Divergence: {avg_kl_div:.4f}")

        # Return metrics as a dictionary
        return {
            'recon_loss': avg_recon_loss,
            'reward_loss': avg_reward_loss,
            'continue_loss': avg_continue_loss,
            'kl_divergence': avg_kl_div
        }
    

    def evaluate_with_grid(self):
        pass

    

