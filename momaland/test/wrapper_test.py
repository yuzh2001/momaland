"""Testing file for the wrappers."""
import numpy as np

import momaland.utils.aec_wrappers as AECWrappers
import momaland.utils.parallel_wrappers as ParallelWrappers


def aec_linearization_test(env_module):
    """Test to see if rewards have been scalarized for the given agents."""
    env = env_module.env()
    weights = {
        env.possible_agents[0]: np.random.dirichlet(np.ones(env.reward_space(env.possible_agents[0]).shape[0]), size=1)[0],
        env.possible_agents[1]: np.random.dirichlet(np.ones(env.reward_space(env.possible_agents[1]).shape[0]), size=1)[0],
    }
    env = AECWrappers.LinearizeReward(env, weights)
    env.reset(seed=42)
    for agent in env.agent_iter():
        observation, reward, termination, truncation, info = env.last()
        if agent is env.possible_agents[0] or agent is env.possible_agents[1]:
            assert len(reward) == 1, "Returned reward should be a scalar value."
        if termination or truncation:
            action = None
        else:
            action = env.action_space(agent).sample()  # this is where you would insert your policy
        env.step(action)
    env.close()


def aec_normalization_test(env_module):
    """Soft test unit. No assertions.

    This test unit is used to check if the API breaks when the wrapper is
    applied, and is also used as an example on how to use the wrapper.

    This code can be taken as example on how to build the `weights` dict.
    """
    env = env_module.env()
    for agent in env.possible_agents:
        for idx in range(env.reward_space(agent).shape[0]):
            env = AECWrappers.NormalizeReward(env, agent, idx)
    env.reset(seed=42)
    for agent in env.agent_iter():
        observation, rewards, termination, truncation, info = env.last()
        print(rewards)
        if termination or truncation:
            action = None
        else:
            action = env.action_space(agent).sample()  # this is where you would insert your policy
        env.step(action)
    assert False
    env.close()


def parallel_linearization_test(env_module):
    """Test to see if rewards have been scalarized for the given agents."""
    env = env_module.parallel_env()
    weights = {
        env.possible_agents[0]: np.random.dirichlet(np.ones(env.reward_space(env.possible_agents[0]).shape[0]), size=1)[0],
        env.possible_agents[1]: np.random.dirichlet(np.ones(env.reward_space(env.possible_agents[1]).shape[0]), size=1)[0],
    }
    env = ParallelWrappers.LinearizeReward(env, weights)
    observations, infos = env.reset(seed=42)
    while env.agents:
        actions = {agent: env.action_space(agent).sample() for agent in env.agents}
        observations, rewards, terminations, truncations, infos = env.step(actions)
        assert (
            len(rewards[env.possible_agents[0]]) == 1 and len(rewards[env.possible_agents[1]]) == 1
        ), "Returned reward should be a scalar value."
    env.close()


def parallel_normalization_test(env_module):
    """Soft test unit. No assertions.

    This test unit is used to check if the API breaks when the wrapper is
    applied, and is also used as an example on how to use the wrapper.

    This code can be taken as example on how to build the `weights` dict.
    """
    env = env_module.parallel_env()
    weights = {
        env.possible_agents[0]: [0, 1],
        env.possible_agents[1]: [0, 1],
    }
    env = ParallelWrappers.NormalizeReward(env, weights)
    observations, infos = env.reset(seed=42)
    while env.agents:
        actions = {agent: env.action_space(agent).sample() for agent in env.agents}
        observations, rewards, terminations, truncations, infos = env.step(actions)
    env.close()


def aec_test(env_module):
    """Testing for the following wrappers for AEC:
    - Normalization
    - Linear Scalarization
    """
    aec_normalization_test(env_module)
    aec_linearization_test(env_module)


def parallel_test(env_module):
    """Testing for the following wrappers for Parallel:
    - Normalization
    - Linear Scalarization
    """
    # parallel_normalization_test(env_module)
    parallel_linearization_test(env_module)


def wrapper_test(env_module):
    """Wrapper testing for AEC and Parallel environments."""
    aec_test(env_module)
    parallel_test(env_module)
