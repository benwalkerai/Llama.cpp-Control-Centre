# LLM Benchmark Tool

A simple Python tool for benchmarking local LLM performance by measuring tokens-per-second generation speed.

## Features

- 🚀 Compatible with any OpenAI-compatible API (Ollama, LM Studio, llama.cpp, vLLM, etc.)
- 📊 Tracks tokens/second, generation time, and token counts
- 💾 Exports results to CSV for easy comparison
- 🎯 Uses consistent prompts for fair benchmarking
- ⚡ Displays real-time spinner animation during tests
- 🔧 Configurable via CLI arguments or `.env` file

## Installation

1. **Clone or download this repository**

2. **Install dependencies:**
```bash
pip install openai python-dotenv
```

3. **Create a `.env` file:**
```env
API_URL=http://localhost:11434/v1
API_KEY=dummy-key
MODEL_NAME=llama3.2:latest
```

## Usage

### Basic Usage

Run with defaults from `.env`:
```bash
python benchmark.py
```

### CLI Arguments

Override settings with command-line arguments:

```bash
# Run 5 benchmark tests
python benchmark.py --runs 5

# Test a different model
python benchmark.py --model llama3.2:1b

# Use a different API endpoint
python benchmark.py --url http://localhost:8080/v1

# Custom output file
python benchmark.py --output my_results.csv

# Combine multiple options
python benchmark.py --model llama3.3:70b --runs 10 --output gpu_test.csv
```

### Available Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--runs` | Number of benchmark runs | 3 |
| `--model` | Model name (overrides .env) | From .env |
| `--url` | API URL (overrides .env) | From .env |
| `--apikey` | API key (overrides .env) | From .env |
| `--output` | Output CSV filename | `benchmark_results.csv` |

## Benchmarking Different Servers

### Ollama

1. Start Ollama:
```bash
ollama serve
```

2. Pull a model:
```bash
ollama pull llama3.2
```

3. Configure `.env`:
```env
API_URL=http://localhost:11434/v1
API_KEY=dummy-key
MODEL_NAME=llama3.2:latest
```

### llama.cpp

1. Start the server with OpenAI compatibility:
```bash
./llama-server --model your-model.gguf --port 8080 --api-key test
```

2. Configure `.env`:
```env
API_URL=http://localhost:8080/v1
API_KEY=test
MODEL_NAME=your-model-name
```

### LM Studio

1. Start LM Studio and load a model
2. Enable the local server (usually port 1234)
3. Configure `.env`:
```env
API_URL=http://localhost:1234/v1
API_KEY=lm-studio
MODEL_NAME=your-model-name
```

## Output

The tool generates a CSV file with the following columns:

- `timestamp` - When the test was run
- `model` - Model name tested
- `run` - Run number
- `prompt_tokens` - Number of input tokens
- `completion_tokens` - Number of generated tokens
- `total_time_seconds` - Total generation time
- `tokens_per_second` - Speed metric
- `time_to_first_token` - N/A (future feature)

### Example Output

```
LLM Benchmark Tool
==================================================
API URL: http://localhost:11434/v1
Model: llama3.2:latest
==================================================

Run 1/3...
 ⠋ Processing...
 Tokens generated: 487
 Time: 12.34s
 Speed: 39.46 tokens/sec

Run 2/3...
 ⠙ Processing...
 Tokens generated: 492
 Time: 12.01s
 Speed: 40.97 tokens/sec

Run 3/3...
 ⠹ Processing...
 Tokens generated: 485
 Time: 12.15s
 Speed: 39.92 tokens/sec

==================================================
BENCHMARK SUMMARY
==================================================
Model: llama3.2:latest
Runs: 3
Avg tokens generated: 488
Avg time: 12.17s
Avg tokens/sec: 40.12
==================================================
```

## Comparing Multiple Models

Create a bash script to test multiple models:

```bash
#!/bin/bash

python benchmark.py --model llama3.2:1b --runs 5
python benchmark.py --model llama3.2:3b --runs 5
python benchmark.py --model llama3.3:70b --runs 5

echo "All benchmarks complete! Check benchmark_results.csv"
```

## Troubleshooting

**Connection Error:**
- Ensure your LLM server is running
- Check the port number matches your server
- Verify the model name is correct

**Missing Environment Variables:**
- Make sure `.env` file exists in the same directory
- Check for typos in variable names
- Ensure no extra spaces around `=` signs

**Model Not Found:**
- For Ollama: Run `ollama list` to see available models
- For llama.cpp: Ensure the model file is loaded
- For LM Studio: Check the model is loaded in the UI

## License

MIT License - Feel free to modify and use as needed!

## Contributing

Issues and pull requests welcome!