#!/usr/bin/env python3
"""Test caller-specific extraction patterns functionality."""

from src.parsers.signal_parser import parse_trading_signal

def test_bendi_pattern():
    """Test Bendi pattern (user_id=468446980)."""
    text = '**BTC 🟢LONG**'
    result = parse_trading_signal(text, user_id=468446980)
    print(f'Bendi pattern (user_id=468446980): {result}')
    assert result['pair'] == 'BTC'
    assert result['direction'] == 'LONG'

def test_underscore_pattern():
    """Test underscore pattern (user_id=740952897)."""
    text = 'BTC_long'
    result = parse_trading_signal(text, user_id=740952897)
    print(f'Underscore pattern (user_id=740952897): {result}')
    assert result['pair'] == 'BTC'
    assert result['direction'] == 'LONG'

def test_simple_pattern():
    """Test simple pattern (user_id=5575681795)."""
    text = 'ETH LONG'
    result = parse_trading_signal(text, user_id=5575681795)
    print(f'Simple pattern (user_id=5575681795): {result}')
    assert result['pair'] == 'ETH'
    assert result['direction'] == 'LONG'

def test_fallback_no_user():
    """Test fallback (no user_id)."""
    text = '#идея SOL/USDT SHORT'
    result = parse_trading_signal(text)
    print(f'Fallback (no user_id): {result}')
    assert result['pair'] == 'SOL/USDT'
    assert result['direction'] == 'SHORT'

if __name__ == '__main__':
    test_bendi_pattern()
    test_underscore_pattern()
    test_simple_pattern()
    test_fallback_no_user()
    print('\nAll tests passed!')
