# expyro 🧪✨

A lightweight Python library to stop your experiments from being a hot mess. Because "it worked on my machine" is not a valid scientific publication.

`expyro` is your new lab assistant 🧑‍🔬 that automatically organizes your chaos: configurations, results, plots, and even that random log file you swear you'll look at later.

## Features at a Glance 👀

*   **🗂️ Structured Experiment Tracking:** No more `final_final_v2_test.py` files. Each run gets its own fancy, timestamped folder. Look organized, even if you're not.
*   **🎯 Type Safety:** Your config isn't just a bunch of random numbers. It's a *well-defined* bunch of random numbers! Thanks, type hints!
*   **♻️ Reproducibility:** Relive the magic (or the horror) of any past run. Perfect for when your advisor asks "can we get the results from last Tuesday?".
*   **📊 Artifact Generation:** Automatically save your beautiful plots and tables. Make your future thesis-writing self cry tears of joy.
*   **💾 Data Capture:** Easily dump any other file (models, logs, a screenshot of your error) right into the experiment's folder.

## Installation 💻

Get the core package and become 10x more organized instantly:

```bash
pip install expyro
```

### Want More? We Got More! 🍟

Level up your experiment-fu with optional extras:

```bash
# For making pretty, pretty plots (matplotlib)
pip install "expyro[matplotlib]"

# For turning results into sweet, sweet tables (pandas)
pip install "expyro[pandas]"

# I want it ALL! 🤑
pip install "expyro[all]"
```

## Quickstart: From Chaos to Clarity in 60 Seconds ⏱️

### 1. Define Your Experiment 🧪

Decorate your experiment function. It's like putting a lab coat on it.

```python
from dataclasses import dataclass
from pathlib import Path
import expyro

# Step 1: Define your config. This is your recipe.
@dataclass
class TrainConfig:
    learning_rate: float = 0.01 # The spice of life
    batch_size: int = 32        # The bigger, the better (until it crashes)
    epochs: int = 10            # The "are we there yet?" parameter

# Step 2: Declare your experiment. Give it a home ("runs/") and a name.
# Your experiment must take exactly one argument as a config.
# The input and output must be typed. 
@expyro.experiment(root=Path("runs"), name="my_awesome_experiment")
def train_model(config: TrainConfig) -> dict[str, float]:
    # Your brilliant (or "it should work") experiment logic goes here.
    final_loss = 0.1 * config.learning_rate
    final_accuracy = 0.9

    # Return whatever you want to remember
    return {"final_loss": final_loss, "final_accuracy": final_accuracy}
```

### 2. Run It! 🏃‍♂️

Call your experiment. Watch the magic happen.

```python
if __name__ == "__main__":
    cfg = TrainConfig(learning_rate=0.01, batch_size=32, epochs=10)
    run = train_model(cfg) # This saves everything! You're welcome.
    print(f"Run completed! Data is chilling in: {run.path}")
```

### 3. Make It Fancy! 🎨

Automatically save plots and tables. Impress everyone.

```python
import matplotlib.pyplot as plt
import pandas as pd

# Artist function: Takes config & result, returns a masterpiece (figure) or even a nested string dict of masterpieces
def create_plot(config: TrainConfig, result: dict) -> plt.Figure:
    fig, ax = plt.subplots()
    ax.bar(["Loss", "Accuracy"], [result["final_loss"], result["final_accuracy"]])
    ax.set_title("How Did We Do?")
    return fig

# Analyst function: Takes config & result, returns a sweet, sweet table (or a nested string dict of tables)
def create_table(config: TrainConfig, result: dict) -> pd.DataFrame:
    return pd.DataFrame([{"metric": k, "value": v} for k, v in result.items()])

# Stack decorators like a pro! The order is bottom-up.
@expyro.plot(create_plot, file_format="pdf") # Save a high-res PDF
@expyro.table(create_table)                  # Save a CSV table
@expyro.experiment(root=Path("runs"), name="fancy_experiment")
def train_and_analyze(config: TrainConfig) -> dict:
    # ... your code ...
    return {"final_loss": 0.1, "final_accuracy": 0.9}
```

### 4. Pre-Bake Configs 🍱

Got favorite settings you keep typing over and over? Stash them as defaults and
summon them later from the command line (see below).

```python
@expyro.defaults({
    "config-1": TrainConfig(learning_rate=0.1, batch_size=32, epochs=5),
    "config-2": TrainConfig(learning_rate=0.001, batch_size=64, epochs=20),
})
@expyro.experiment(root=Path("runs"), name="experiment_with_defaults")
def train_with_defaults(config: TrainConfig) -> dict:
    # ... your code ...
    return {"final_loss": 0.1}
```

### 5. Save ALL THE THINGS! 💾

Use `hook` to save anything else right into the experiment's folder.

```python
@expyro.experiment(root=Path("runs"), name="experiment_with_everything")
def train_with_logging(config: TrainConfig) -> dict:
    # Save a log file
    with expyro.hook("logs/training_log.txt", "w") as f:
        f.write(f"Let's hope this LR {config.learning_rate} works...\n")
        f.write("Epoch 1: Loss=0.5 😬\n")
        f.write("Epoch 2: Loss=0.2 😊\n")

    # Save a model file (pytorch example)
    # with expyro.hook("best_model.pt", "wb") as f:
    #    torch.save(model.state_dict(), f)

    return {"final_loss": 0.1}
```

### 6. Analyze Your Glory (or Mistakes) 🔍

Iterate over past runs like a data archaeologist.

```python
# Your experiment is now also a container for all its runs!
my_experiment = train_model # This is your decorated function

print("Behold, all my past runs:")
for run in my_experiment: # 🚀 Iterate over everything!
    print(f"Run {run.path.name}: Config={run.config}, Result={run.result}")

# Load a specific run from its path
that_one_run = my_experiment["2024-05-27/12:30:45.123 abcdef00"]
print(f"Ah yes, the run where loss was: {that_one_run.result['final_loss']}")
```

## What's In The Box? 📦 (The Project Structure)

Here’s how `expyro` organizes your brilliance:

```
runs/
└── my_awesome_experiment/    # Your experiment name
    └── 2024-05-27/           # The date (so you know when you did the work)
        ├── 12:30:45.123 abcdef00/        # Time & unique ID (so you can find it)
        │   ├── config.pickle             # 🗃️ Your configuration, pickled.
        │   ├── result.pickle             # 📊 Your results, also pickled.
        │   ├── artifacts/
        │   │   ├── plots/                # 🎨 Home for your beautiful graphs
        │   │   │   └── create_plot.pdf
        │   │   └── tables/               # 📋 Home for your elegant tables
        │   │       └── create_table.csv
        │   └── data/                     # 💾 Your custom files live here (from `hook`)
        │       └── logs/
        │           └── training_log.txt
        └── 14:22:10.456 1a2b3c4d/        # Another run! You've been busy!
            ├── config.pickle
            └── result.pickle
```

## CLI Time Travel Machine ⏳💻

Prefer the command line life? `expyro` scans your project for decorated experiments and hands each one its own
subcommand. It's like giving every lab rat a keyboard. 🐀

```
# Run a fresh experiment
expyro my_awesome_experiment run --learning-rate 0.01 --batch-size 32

# Kick off a run using a pre-baked config
expyro my_awesome_experiment default config-1

# Reproduce an old run with the exact same config
expyro my_awesome_experiment reproduce "2024-05-27/12:30:45.123 abcdef00"

# Redo an artifact when you forgot to save that plot 🎨
expyro my_awesome_experiment redo plots "2024-05-27/12:30:45.123 abcdef00"
```

Why so many verbs? Because reproducibility is king 👑:

* **`run`** starts a brand-new adventure and saves everything.
* **`default`** grabs a config registered with `@expyro.defaults` and runs it - no flags needed.
* **`reproduce`** reruns an experiment with the original config, giving you a carbon-copy run for free.
* **`redo`** regenerates plots or tables for an existing run, so you can tweak your visuals without touching the 
science.

All from the shell, all consistent, all reproducible. 🔁

For detailed information for your specific setup, run

```bash
expyro --help
```

from the root directory of your project.

## License 📄

MIT License. Go forth and experiment! Just maybe use this library first.

---

**Now go forth and reproduce!** 🚀

