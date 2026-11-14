"""판단 점검표 6단계.

① 사업 분해 → ② 규제 탐색(위임 사슬·원문 대조) → ③ 규제 유형 판정 → ④ 소관 판별
→ ⑤ 선례 대조(승인 사례·불의타 신호) → ⑥ 트랙 제안·창구 선택

각 단계는 근거(Evidence)를 하나 이상 내야 다음 단계로 넘어간다.
"""

from .runner import STAGES, run
from .types import CaseState, Evidence, EvidenceGateError, StageResult

__all__ = ["run", "STAGES", "CaseState", "Evidence", "StageResult", "EvidenceGateError"]
