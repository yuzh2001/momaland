"""Implementation of stateless independent Q-learners. Implemented for the multi-objective congestion game and beach domain."""

import random

import numpy as np
from gymnasium.spaces import Discrete

from momaland.envs.beach_domain.beach_domain import (
    MOBeachDomain,
    _global_capacity_reward,
    _global_mixture_reward,
)


# from momaland.envs.congestion_game import mocongestion_v0 as CongestionGame


class TabularMOBeachDomainWrapper(MOBeachDomain):
    """Wrapper for the MO-beach domain environment to return only the current beach section as state.

    MO-Beach domain returns 5 observations in each timestep:
        - agent type
        - section id
        - section capacity
        - section consumption
        - % of agents of current type
    In the original paper however tabular Q-learning is used and therefore only the current beach section is used as
    the state. This provide allows to compare results of the original paper:

    From Mannion, P., Devlin, S., Duggan, J., and Howley, E. (2018). Reward shaping for knowledge-based multi-objective multi-agent reinforcement learning.
    """

    def __init__(self, **kwargs):
        """Initialize the wrapper.

        Initialize the wrapper and set the observation space to be a discrete space with the number of sections as
        possible states.

        Args:
            **kwargs: keyword arguments for the MO-beach domain environment
        """
        self.l_cap_min, self.l_cap_max, self.l_mix_min, self.l_mix_max = kwargs.pop("local_constants")
        self.g_cap_min, self.g_cap_max, self.g_mix_min, self.g_mix_max = kwargs.pop("global_constants")
        super().__init__(**kwargs)

        self.observation_spaces = dict(
            zip(
                self.agents,
                [
                    Discrete(
                        self.sections,
                    )
                ],
            )
        )

    def normalize_objective_rewards(self, reward, reward_scheme):
        """Normalize the rewards based on the reward scheme.

        Args:
            reward: the reward to normalize
            reward_scheme: the reward scheme to use

        Returns:
            np.array: the normalized reward
        """
        # Set the normalization constants
        if reward_scheme == "local":
            cap_min, cap_max, mix_min, mix_max = self.l_cap_min, self.l_cap_max, self.l_mix_min, self.l_mix_max
        else:
            cap_min, cap_max, mix_min, mix_max = self.g_cap_min, self.g_cap_max, self.g_mix_min, self.g_mix_max

        # Normalize the rewards
        cap_norm = (reward[0] - cap_min) / (cap_max - cap_min)
        mix_norm = (reward[1] - mix_min) / (mix_max - mix_min)

        return np.array([cap_norm, mix_norm])

    def step(self, actions):
        """Step function of the environment.

        Intercepts the observations and returns only the section id as observation.
        Also computes the global rewards and normalizes them.

        Args:
            actions: dict of actions for each agent

        Returns:
            observations: dict of observations for each agent
            rewards: dict of rewards for each agent
            terminations: dict of terminations for each agent
            truncations: dict of truncations for each agent
            infos: dict of infos for each agent
        """
        observations, rewards, terminations, truncations, infos = super().step(actions)
        # Observations: agent type, section id, section capacity, section consumption, % of agents of current type
        # Instead we want to only extract the section id
        observations = {agent: int(obs[1]) for agent, obs in observations.items()}

        # Compute global rewards in order to report them in the info dict
        section_consumptions = np.zeros(self.sections)
        section_agent_types = np.zeros((self.sections, len(self.type_distribution)))

        for i in range(len(self.possible_agents)):
            section_consumptions[self._state[i]] += 1
            section_agent_types[self._state[i]][self._types[i]] += 1
        g_capacity = _global_capacity_reward(self.resource_capacities, section_consumptions)
        g_mixture = _global_mixture_reward(section_agent_types)
        g_capacity_norm, g_mixture_norm = self.normalize_objective_rewards(np.array([g_capacity, g_mixture]), "global")
        infos = {
            agent: {"g_cap": g_capacity, "g_mix": g_mixture, "g_cap_norm": g_capacity_norm, "g_mix_norm": g_mixture_norm}
            for agent in self.possible_agents
        }

        # Normalize the rewards
        for agent in self.possible_agents:
            rewards[agent] = self.normalize_objective_rewards(rewards[agent], self.reward_scheme)

        return observations, rewards, terminations, truncations, infos

    def reset(self, seed=None, options=None):
        """Reset function of the environment.

        Intercepts the observations and returns only the section id as observation.

        Args:
            seed: seed for the environment
            options: options for the environment

        Returns:
            observations: dict of observations for each agent
            infos: dict of infos for each agent
        """
        observations, infos = super().reset(seed=seed, options=options)
        # Observations: agent type, section id, section capacity, section consumption, % of agents of current type
        # Instead we want to only extract the section id
        observations = {agent: int(obs[1]) for agent, obs in observations.items()}
        return observations, infos


def compute_utility(weights, rewards):
    """Compute the utility of a given action based on the weights and the rewards of the objectives.

    Args:
        weights: the weights for the objectives
        rewards: the rewards for the objectives

    Returns:
        float: the utility of the action
    """
    return np.dot(weights, rewards)


class QAgent:
    """Q-learning agent."""

    def __init__(self, agent_id, n_states, n_actions):
        """Initialize the Q-agent."""
        self.agent_id = agent_id
        self.n_states = n_states
        self.n_actions = n_actions
        self.q_values = np.zeros((n_states, n_actions), dtype=np.float32)

    def act(self, state, epsilon):
        """Epsilon-greedy action selection.

        Choose the action with the highest Q-value with probability 1-epsilon otherwise choose a random action.
        """
        if np.random.random() < epsilon:
            return np.random.randint(0, self.n_actions)
        else:
            return np.argmax(self.q_values[state])

    def update(self, state, new_state, action, alpha, gamma, reward, done):
        """Update the Q-values of the agent based on the chosen action and the new state."""
        # Retrieve the current Q-value
        q_value = self.q_values[state][action]
        # Compute the next max Q-value
        next_max_q_value = 0.0 if done else np.max(self.q_values[new_state])
        self.q_values[state][action] = q_value + alpha * (reward + gamma * next_max_q_value - q_value)


def train(args, weights, env_args):
    """IQL scalarizing the vector reward using weights and weighted sum."""
    # Environment Initialization
    env = TabularMOBeachDomainWrapper(**env_args)
    obs, infos = env.reset()

    agents = {
        QAgent(agent_id, env.observation_space(env.agents[0]).n, env.action_spaces[agent_id].n)
        for agent_id in env.possible_agents
    }

    # Algorithm specific parameters
    epsilon = args.epsilon
    epsilon_decay = args.epsilon_decay
    epsilon_min = args.epsilon_min
    alpha = args.alpha
    alpha_decay = args.alpha_decay
    alpha_min = args.alpha_min
    gamma = args.gamma

    episode_returns = []
    # keep track of the best reward encountered
    best_reward = np.array([-np.inf, -np.inf])
    best_reward_scal = -np.inf

    for current_iter in range(args.num_iterations):
        # Get the actions from the agents
        if args.random:
            actions = {q_agent.agent_id: random.choice(range(env.action_spaces[q_agent.agent_id].n)) for q_agent in agents}
        else:
            actions = {q_agent.agent_id: q_agent.act(obs[q_agent.agent_id], epsilon) for q_agent in agents}

        # Update the exploration rate
        if epsilon > epsilon_min:
            epsilon *= epsilon_decay
        else:
            epsilon = epsilon_min

        new_obs, rew, terminateds, truncations, infos = env.step(actions)

        # Check if all agents are terminated (in a stateless setting, this is always the case)
        terminated = np.logical_or(
            np.any(np.array(list(terminateds.values())), axis=-1), np.any(np.array(list(truncations.values())), axis=-1)
        )

        # Update the Q-values of the agents
        for agent in agents:
            agent.update(
                obs[agent.agent_id],
                new_obs[agent.agent_id],
                actions[agent.agent_id],
                alpha,
                gamma,
                compute_utility(weights, rew[agent.agent_id]),
                terminated,
            )

        if env.metadata["name"] == "mobeach_v0":
            # MO-Beach domain reports the global rewards in the info dict, regardless of the reward scheme
            avg_obj1 = infos[env.possible_agents[0]]["g_cap"]
            avg_obj2 = infos[env.possible_agents[0]]["g_mix"]

            avg_obj1_norm = infos[env.possible_agents[0]]["g_cap_norm"]
            avg_obj2_norm = infos[env.possible_agents[0]]["g_mix_norm"]

            # Keep track of best reward during training
            new_reward = np.array([avg_obj1, avg_obj2])
            scal_rew = compute_utility(weights, np.array([avg_obj1_norm, avg_obj2_norm]))
            episode_returns.append((current_iter, avg_obj1_norm, avg_obj2_norm, scal_rew))
        else:
            avg_obj1 = np.mean(np.array(list(rew.values()))[:, 0])
            avg_obj2 = np.mean(np.array(list(rew.values()))[:, 1])
            scal_rew = compute_utility(weights, np.array([avg_obj1, avg_obj2]))
            episode_returns.append((current_iter, avg_obj1, avg_obj2, scal_rew))

        if scal_rew > best_reward_scal:
            best_reward = new_reward
            best_reward_scal = scal_rew

        # Update the learning rate
        if alpha > alpha_min:
            alpha *= alpha_decay
        else:
            alpha = alpha_min

        # In case of termination, reset the environment
        if terminated:
            env.reset()

    metric = {"returned_episode_returns": np.array(episode_returns), "best_reward": best_reward}
    return {"metrics": metric}
