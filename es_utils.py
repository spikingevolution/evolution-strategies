import json
import gym
import os

from collections import namedtuple
from enum import Enum
from pathlib import Path

class ConfigValues(Enum):
    OPTIMIZER_ADAM = 'adam'
    OPTIMIZER_SGD = 'sgd'
    RETURN_PROC_MODE_CR = 'centered_rank'
    RETURN_PROC_MODE_SIGN = 'sign'
    RETURN_PROC_MODE_CR_SIGN = 'centered_sign_rank'

Config = namedtuple('Config', [
    'env_id',
    'population_size',
    'timesteps_per_gen',
    'num_workers',
    'learning_rate',
    'noise_stdev',
    'snapshot_freq',
    'return_proc_mode',
    'calc_obstat_prob',
    'l2coeff',
    'eval_prob'
])

Optimizations = namedtuple('Optimizations', [
    'mirrored_sampling',
    'fitness_shaping',
    'weight_decay',
    'discretize_actions',
    'gradient_optimizer',
    'observation_normalization',
    'divide_by_stdev'
])

ModelStructure = namedtuple('ModelStructure', [
    'ac_noise_std',
    'ac_bins',
    'hidden_dims',
    'nonlin_type',
    'optimizer',
    'optimizer_args'
])

class InvalidTrainingError(Exception):
    # TODO own file
    pass

def validate_config(config_input):
    """
    Creates an Optimizations, ModelStructure and Config object from config_input and validates their attributes.

    config_input must be of type os.DirEntry or dict. It will try to create the respective objects from the dict
    entries it reads from the input. Afterwards the values get validated. If everything is valid the objects get
    returned, otherwise an InvalidTrainingError is raised.

    :param config_input: Configuration input of type os.DirEntry or dict
    :raises InvalidTrainingError: Will be raised when no valid objects can be created
    :return: A Valid Optimizations, ModelStructure and Config object, in this order
    """
    # Only os.DirEntry and dict are supported as input files. Could be easily extended if needed
    if isinstance(config_input, os.DirEntry):
        with open(config_input.path, encoding='utf-8') as f:
            try:
                config_dict = json.load(f)
            except json.JSONDecodeError:
                raise InvalidTrainingError("The config file {} cannot be parsed.".format(config_input.path))
    elif isinstance(config_input, dict):
        config_dict = config_input
    else:
        raise InvalidTrainingError("The input format of {} is not valid.".format(config_input))

    # Load the dictionary entries for the optimizations, model structure and the overall config
    try:
        optimization_dict = config_dict["optimizations"]
        model_structure_dict = config_dict["model_structure"]
        _config_dict = config_dict["config"]
    except KeyError:
        raise InvalidTrainingError("The loaded config does not have an entry for either the optimizations, model structure or the config.")

    # Create the Optimizations, ModelStructure and Config objects from the respective dict. If the keys in these
    # dicts are valid no exception is raised
    try:
        optimizations = Optimizations(**optimization_dict)
        model_structure = ModelStructure(**model_structure_dict)
        config = Config(**_config_dict)
    except TypeError:
        raise InvalidTrainingError("Cannot initialize the Optimizations object from {}".format(optimization_dict))

    # Now check the values for the created objects
    try:
        validate_config_objects(optimizations, model_structure, config)
    except InvalidTrainingError:
        raise

    return optimizations, model_structure, config

def validate_config_objects(optimizations, model_structure, config):
    """
    Validates the values of already created configuration objects.

    The inputs must be of Type Optimizations, ModelStructure and Config. If at least one of their values is invalid,
    a InvalidTrainingError is raised.

    :param optimizations: An object of type Optimizations for which the values shall be validated
    :param model_structure: An object of type ModelStructure for which the values shall be validated
    :param config: An object of type Config for which the values shall be validated
    :raises InvalidTrainingError: When there is at least one invalid value
    """

    if not isinstance(optimizations, Optimizations) or not isinstance(model_structure, ModelStructure) or not isinstance(config, Config):
        raise InvalidTrainingError("One of the given arguments has a false type.")

    # Check if the values for the optimizations are valid
    if not all(isinstance(v, bool) for v in optimizations):
        raise InvalidTrainingError("The values from {} cannot be used to initialize an Optimization object".format(optimizations))

    # Validate values for the ModelStructure object
    try:
        assert model_structure.ac_noise_std >= 0
        assert isinstance(model_structure.hidden_dims, list)
        assert all(isinstance(entry, int) for entry in model_structure.hidden_dims)
        assert all(hd > 0 for hd in model_structure.hidden_dims)
        assert isinstance(model_structure.nonlin_type, str)
        if optimizations.gradient_optimizer:
            # Other values in the optimizer_args dict are not checked only the mandatory stepsize is there
            # Could potentially lead to false arguments. They are handled in the Optimizer class
            assert model_structure.optimizer == ConfigValues.OPTIMIZER_ADAM or model_structure.optimizer == ConfigValues.OPTIMIZER_SGD
            stepsize = model_structure.optimizer_args['stepsize']
            assert stepsize > 0
        if optimizations.discretize_actions:
            assert model_structure.ac_bins > 0
    except KeyError:
        raise InvalidTrainingError("The model structure is missing the stepsize for the gradient optimizer.")
    except TypeError or AssertionError:
        raise InvalidTrainingError("One or more of the given values for the model structure is not valid.")

    # Validate values for the config
    try:
        # Testing if the ID is valid by creating an environment with it
        gym.make(config.env_id)
    except:
        raise InvalidTrainingError("The provided environment ID {} is invalid.".format(config.env_id))

    try:
        assert config.population_size > 0
        assert config.timesteps_per_gen > 0
        assert config.num_workers > 0
        assert config.learning_rate > 0
        assert config.noise_stdev != 0
        assert config.snapshot_freq >= 0
        assert config.eval_prob >= 0

        assert (config.return_proc_mode == ConfigValues.RETURN_PROC_MODE_CR
                or config.return_proc_mode == ConfigValues.RETURN_PROC_MODE_SIGN
                or config.return_proc_mode == ConfigValues.RETURN_PROC_MODE_CR_SIGN)

        if optimizations.observation_normalization:
            assert config.calc_obstat_prob > 0

        if optimizations.gradient_optimizer:
            assert config.l2coeff > 0
    except TypeError or AssertionError:
        raise InvalidTrainingError("One or more of the given values for the config is not valid.")

def index_training_folder(training_folder):
    '''
    Indexes a given training folder and returns a resulting TrainingRun object.

    The function first searches for the config, validates it and creates a dictionary from it. If no valid config
    is created a InvalidTrainingException is raised, because the config is mandatory to determine a TrainingRun.
    After that the log, evaluation, model and other saved files are indexed and validated. If they are valid, they
    get saved as attributes in the TrainingRun object, which then gets returned.

    :param training_folder: The folder which contains a started training which shall be loaded
    :return: A TrainingRun object with the attributes set to valid objects found in the training_folder
    :raises: InvalidTrainingException if the config files is not found or invalid
    '''

    # 1. Check if folder
    # 2. Indexiere Dateien
    # -> alles als Objekt speichern
    # 3. Validiere config

    #return TrainingRun()

    if not os.path.isdir(training_folder):
        raise InvalidTrainingError("Cannot load training, {} is not a directory.".format(training_folder))

    with os.scandir(training_folder) as it:
        for entry in it:
            if entry.name.endswith(".h5") and entry.is_file():
                # TODO
                pass
            elif entry.name == "config.json" and entry.is_file():
                config_file = entry

    validate_config(config_file)

    p = Path(training_folder)

    config_file = p / "config.json"

    if not config_file.is_file():
        raise InvalidTrainingError("Cannot load training, no config.json found in directory {}".format(training_folder))

    with config_file.open() as f:
        test = f

    model_files = list(p.glob("*.h5"))

    index = {}
    # for root, dirs, files in os.walk(main_directory):
    #     if 'log.csv' in files and 'config.json' in files:
    #         index[root] = files
    #
    # training_runs = []
    # for sub_dir in index:
    #     models, log, evaluation, config, video_file = [], None, None, None, None
    #     for file in index[sub_dir]:
    #         if file.endswith('.h5'):
    #             models.append(file)
    #             continue
    #         elif file.endswith('log.csv'):
    #             try:
    #                 log = pd.read_csv(os.path.join(sub_dir, file))
    #             except pd.errors.EmptyDataError:
    #                 print("The log file {} is empty. Skipping this folder({}).".format(
    #                     file, sub_dir))
    #             continue
    #         elif file.endswith('evaluation.csv'):
    #             try:
    #                 evaluation = pd.read_csv(os.path.join(sub_dir, file))
    #             except pd.errors.EmptyDataError:
    #                 print("The evaluation file {} is empty. Continuing.".format(file))
    #             continue
    #         elif file.endswith('config.json'):
    #             with open(os.path.join(sub_dir, file), encoding='utf-8') as f:
    #                 try:
    #                     config = json.load(f)
    #                 except json.JSONDecodeError as e:
    #                     print("The config file {} is empty or cannot be parsed. Skipping this folder ({}).".format(
    #                         file, sub_dir))
    #             continue
    #         elif file.endswith('.mp4'):
    #             video_file = os.path.join(sub_dir, file)
    #             continue
    #     models.sort()
    #     if log is not None and config is not None:
    #         training_runs.append(TrainingRun(sub_dir, log, config, models, evaluation, video_file))
    #
    # configs_and_runs = []
    # for run in training_runs:
    #     found = False
    #     for c in configs_and_runs:
    #         if c[0] == run.config:
    #             c[1].append(run)
    #             found = True
    #             break
    #
    #     if not found:
    #         configs_and_runs.append((run.config, [run]))
    #
    # return [Experiment(config, runs) for (config, runs) in configs_and_runs]
    #

def main():
    training_folder = "training_runs/11_11_2019-17h_19m_00s"
    index_training_folder(training_folder)

if __name__ == "__main__":
    main()

class TrainingRun:
    pass