"""Shared-wallet integration for verified historical futures campaigns."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apex.application.historical_signal_io import load_historical_signal_record_payloads
from apex.backtesting.historical_futures_campaign import (
    Historical