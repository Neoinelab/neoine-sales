"""독립 Excel 도구를 테스트에서 import한다."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "excel-upload"))
