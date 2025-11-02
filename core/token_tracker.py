"""
Token and cost tracking for AI API calls
Provides detailed visibility into AI usage and costs
"""

from datetime import datetime
from typing import Dict, List, Optional
import json


class TokenTracker:
    """Track AI API usage, tokens, and costs"""

    # Pricing per million tokens (as of Jan 2025)
    PRICING = {
        'claude-sonnet-4-5-20250929': {
            'input': 3.00,   # $3 per million input tokens
            'output': 15.00  # $15 per million output tokens
        },
        'claude-haiku-4-5-20251001': {
            'input': 1.00,   # $1 per million input tokens
            'output': 5.00   # $5 per million output tokens
        }
    }

    def __init__(self):
        self.calls = []
        self.session_start = datetime.now()

    def log_call(self,
                 operation: str,
                 model: str,
                 input_tokens: int,
                 output_tokens: int,
                 metadata: Optional[Dict] = None):
        """
        Log an AI API call

        Args:
            operation: Description of what this call did (e.g., "email_classification", "event_extraction")
            model: Model name used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            metadata: Optional metadata (email_id, event_count, etc.)
        """
        # Calculate cost
        pricing = self.PRICING.get(model, {'input': 0, 'output': 0})
        input_cost = (input_tokens / 1_000_000) * pricing['input']
        output_cost = (output_tokens / 1_000_000) * pricing['output']
        total_cost = input_cost + output_cost

        call_record = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': input_tokens + output_tokens,
            'cost': total_cost,
            'metadata': metadata or {}
        }

        self.calls.append(call_record)

    def get_summary(self) -> Dict:
        """Get summary statistics for the session"""
        if not self.calls:
            return {
                'total_calls': 0,
                'total_cost': 0,
                'total_tokens': 0
            }

        # Group by operation type
        operations = {}
        for call in self.calls:
            op = call['operation']
            if op not in operations:
                operations[op] = {
                    'count': 0,
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'total_tokens': 0,
                    'cost': 0.0,
                    'model': call['model']
                }

            operations[op]['count'] += 1
            operations[op]['input_tokens'] += call['input_tokens']
            operations[op]['output_tokens'] += call['output_tokens']
            operations[op]['total_tokens'] += call['total_tokens']
            operations[op]['cost'] += call['cost']

        # Calculate totals
        total_calls = len(self.calls)
        total_input = sum(c['input_tokens'] for c in self.calls)
        total_output = sum(c['output_tokens'] for c in self.calls)
        total_tokens = sum(c['total_tokens'] for c in self.calls)
        total_cost = sum(c['cost'] for c in self.calls)

        # Session duration
        duration = (datetime.now() - self.session_start).total_seconds()

        return {
            'session_start': self.session_start.isoformat(),
            'session_duration_seconds': duration,
            'total_calls': total_calls,
            'total_input_tokens': total_input,
            'total_output_tokens': total_output,
            'total_tokens': total_tokens,
            'total_cost': total_cost,
            'operations': operations,
            'calls': self.calls  # Detailed call log
        }

    def print_summary(self):
        """Print a formatted summary to console"""
        summary = self.get_summary()

        if summary['total_calls'] == 0:
            print("\n[*] No AI calls made this session")
            return

        print("\n" + "=" * 80)
        print("AI TOKEN USAGE SUMMARY")
        print("=" * 80)

        # Session info
        duration_min = summary['session_duration_seconds'] / 60
        print(f"\nSession Duration: {duration_min:.1f} minutes")
        print(f"Total API Calls: {summary['total_calls']}")
        print(f"Total Tokens: {summary['total_tokens']:,}")
        print(f"  - Input: {summary['total_input_tokens']:,}")
        print(f"  - Output: {summary['total_output_tokens']:,}")
        print(f"Total Cost: ${summary['total_cost']:.4f}")

        # Breakdown by operation
        print("\n" + "-" * 80)
        print("BREAKDOWN BY OPERATION:")
        print("-" * 80)

        for operation, stats in summary['operations'].items():
            avg_cost = stats['cost'] / stats['count'] if stats['count'] > 0 else 0
            print(f"\n{operation}:")
            print(f"  Model: {stats['model']}")
            print(f"  Calls: {stats['count']}")
            print(f"  Tokens: {stats['total_tokens']:,} (in: {stats['input_tokens']:,}, out: {stats['output_tokens']:,})")
            print(f"  Cost: ${stats['cost']:.4f} (avg: ${avg_cost:.4f} per call)")

        # Cost breakdown
        print("\n" + "-" * 80)
        print("COST BREAKDOWN:")
        print("-" * 80)
        for operation, stats in sorted(summary['operations'].items(), key=lambda x: x[1]['cost'], reverse=True):
            percentage = (stats['cost'] / summary['total_cost'] * 100) if summary['total_cost'] > 0 else 0
            print(f"  {operation}: ${stats['cost']:.4f} ({percentage:.1f}%)")

        print("\n" + "=" * 80)

    def save_to_file(self, filepath: str = 'ai_usage_log.json'):
        """Save detailed log to JSON file"""
        summary = self.get_summary()

        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"[+] Detailed AI usage log saved to: {filepath}")
