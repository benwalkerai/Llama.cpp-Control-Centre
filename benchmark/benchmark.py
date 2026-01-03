import os
import time
import csv
import threading
import itertools
import sys
import argparse
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configurations from .env
API_URL = os.getenv("API_URL")
API_KEY = os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")

# Validate that variables loaded
if not API_URL or not MODEL_NAME:
    raise ValueError("Missing required environment variables. Check your .env file!")

# Standard benchmark prompt
BENCHMARK_PROMPT = """
Write a detailed explanation of how neural networks learn through backpropagation.
Include the mathematical concepts and provide examples.
"""

# CSV file to store results
CSV_FILE = "benchmark_results.csv"

# Running animation
def spinner(stop_event):
    """Display a spinner animation"""
    spinner_chars = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
    while not stop_event.is_set():
        sys.stdout.write(f'\r {next(spinner_chars)} Processing...')
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write('\r')
    sys.stdout.flush()

def run_benchmark(num_runs=3):
    """Run benchmark test and return results"""

    client = OpenAI(
        base_url=API_URL,
        api_key=API_KEY,
    )

    results = []

    for run in range(1, num_runs + 1):
        print(f"\nRun {run}/{num_runs}...")
        try:
            # Start the spinner
            stop_spinner = threading.Event()
            spinner_thread = threading.Thread(target=spinner, args=(stop_spinner,))
            spinner_thread.start()

            start_time = time.time()
            response = client.chat.completions.create(model = MODEL_NAME, messages = [{"role": "user", "content": BENCHMARK_PROMPT}], max_tokens=500, temperature=0.7,stream=False,)

            end_time = time.time()

            # Stop spinner
            stop_spinner.set()
            spinner_thread.join()
        
            # Calculate metrics
            total_time = end_time - start_time
            tokens_generated = response.usage.completion_tokens
            prompt_tokens = response.usage.prompt_tokens
            tokens_per_second = tokens_generated / total_time if total_time > 0 else 0

            result = {
                "timestamp": datetime.now().isoformat(),
                "model": MODEL_NAME,
                "run": run,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": tokens_generated,
                "total_time_seconds": round(total_time, 2),
                "tokens_per_second": round(tokens_per_second, 2),
                "time_to_first_token": "N/A"
            }

            results.append(result)

            print(f" Tokens generated: {tokens_generated}")
            print(f" Time: {total_time:.2f}s")
            print(f" Speed: {tokens_per_second:.2f} tokens/sec")
        except Exception as e:
            print(f" Error during run {run}: {e}")
            continue
    return results

def save_to_csv(results):
    """ Append results to CSV file"""

    file_exists = Path(CSV_FILE).exists()

    fieldnames = [
        "timestamp", "model", "run", "prompt_tokens", "completion_tokens", "total_time_seconds", "tokens_per_second", "time_to_first_token"
    ]

    with open(CSV_FILE, 'a', newline='') as f:
        writer =csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()
        writer.writerows(results)
    print(f"\nResults appended to {CSV_FILE}")

def print_summary(results):
    """Prints summary statistics"""

    if not results:
        print("No results to summarize")
        return
    
    avg_tokens = sum(r["completion_tokens"] for r in results) /len(results)
    avg_time = sum(r["total_time_seconds"] for r in results) / len(results)
    avg_tps = sum(r["tokens_per_second"] for r in results) / len(results)

    print("\n" + "="*50)
    print("BENCHMARK SUMMARY")
    print("="*50)
    print(f"Model: {MODEL_NAME}")
    print(f"Runs: {len(results)}")
    print(f"Avg tokens generated: {avg_tokens:.0f}")
    print(f"Avg time: {avg_time:.2f}s")
    print(f"Avg tokens/sec: {avg_tps:.2f}")
    print("="*50)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark LLM models")
    parser.add_argument("--runs", type=int, default=3, help="Number of benchmark runs")
    parser.add_argument("--model", type=str, help="Override model from .env")
    parser.add_argument("--url", type=str, help="Override API URL from .env")
    parser.add_argument("--apikey", type=str, help="Override API Key from .env")
    parser.add_argument("--output", type=str, default="benchmark_results.csv")
    args = parser.parse_args()

    # Override with CLI args if provided
    if args.model:
        MODEL_NAME = args.model
    if args.url:
        API_URL = args.url
    if args.apikey:
        API_KEY = args.apikey
    
    CSV_FILE = args.output

    print("LLM Benchmark Tool")
    print("="*50)
    print(f"API URL: {API_URL}")
    print(f"Model: {MODEL_NAME}")
    print("="*50)

    # run benchmark
    results = run_benchmark(num_runs=3)

    if results:
        # Save to CSV
        save_to_csv(results)

        # Print summary
        print_summary(results)
    else:
        print("\nNo successful runs completed")