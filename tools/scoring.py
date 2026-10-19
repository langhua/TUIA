"""TUIA 可及性评分模型。

思路：一个核素"能不能用"，取决于它挡住你的最短那块板。因此评分不是简单加权，
而是「加权平均 × 短板折损」：

    TUIA = Base × (0.60 + 0.40 × min_i(S_i) / 100)

其中 Base = Σ w_i · S_i（七个子维度），min_i 为最差子维度。
这样"丰度极高但完全无法分离"与"能分离但要一克一万美元"都会被正确压低。

七个子维度
----------
A1 天然丰度     同位素在自然界的现成比例（对数刻度）
A2 分离/生产难度  富集或核合成路线的工艺门槛
A3 成本         每毫摩尔/每毫克的价格量级
A4 可得量级     全球年可供应的批量（质量或活度）
A5 供应成熟度    是否商业化、是否有稳定供应商与货期
A6 管制负担     放射性许可、核材料保障、运输与辐照管理
A7 纯化上限     可达到的同位素纯度（对 NV 色心一类应用是一票否决项）
"""

from __future__ import annotations

import math

# ------------------------------------------------------------------ 权重

WEIGHTS: list[tuple[str, str, float]] = [
    ("A1", "天然丰度", 0.15),
    ("A2", "分离/生产难度", 0.20),
    ("A3", "成本量级", 0.20),
    ("A4", "可得量级", 0.15),
    ("A5", "供应成熟度", 0.10),
    ("A6", "管制负担", 0.08),
    ("A7", "纯化上限", 0.12),
]

# ------------------------------------------------------------------ 映射表

# 富集/生产工艺类别 -> (A2 生产难度分, A7 纯化上限分, 典型纯度)
METHOD_SCORE: dict[str, tuple[float, float, str]] = {
    "无需富集":      (100, 100, "天然即纯"),
    "低温蒸馏":      (72, 85, "99.9%"),
    "化学交换":      (70, 85, "99.9%"),
    "气体离心":      (62, 90, "99.9%"),
    "离子交换色谱":  (45, 75, "99%"),
    "热扩散":        (55, 65, "99%"),
    "电磁分离":      (22, 88, "99.99%"),
    "激光分离":      (18, 80, "99.9%"),
    "反应堆活化":    (55, 55, "载体依赖性"),
    "裂变产物分离":  (58, 70, "98%"),
    "发生器洗脱":    (60, 65, "载体依赖性"),
    "加速器合成":    (30, 50, "放射化学纯"),
    "加速器合成（常规）": (70, 60, "药品级放射化学纯"),
    "散裂/放射性束": (15, 20, "原子级"),
}

# 已产业化的加速器核素：几十台商用回旋器每天在产，和 ²¹¹At / ²²⁵Ac 这种
# 全世界一两台装置的产物不是同一回事。原来两者共用一个 A2=30，
# 导致 ¹⁸F（全球日产千居）与 ²²⁵Ac（年产不足百居）几乎同分。
ACCEL_ROUTINE: frozenset[str] = frozenset({
    "18F", "11C", "13N", "15O",          # 短半衰期 PET 四件套，医院就地生产
    "68Ga", "89Zr", "64Cu", "111In", "123I", "201Tl",   # 商用回旋/发生器产物
})

# 元素 enrich 字段里的写法 -> METHOD_SCORE 的键
METHOD_ALIAS: list[tuple[str, str]] = [
    ("电磁分离", "电磁分离"),
    ("激光分离", "激光分离"),
    ("气体离心", "气体离心"),
    ("低温蒸馏", "低温蒸馏"),
    ("化学交换", "化学交换"),
    ("离子交换色谱", "离子交换色谱"),
    ("热扩散", "热扩散"),
    ("裂变产物分离", "裂变产物分离"),
    ("发生器洗脱", "发生器洗脱"),
    ("加速器合成", "加速器合成"),
    ("反应堆活化", "反应堆活化"),
    ("散裂/放射性束", "散裂/放射性束"),
]

TIER_SCORE = {0: 100, 1: 82, 2: 62, 3: 38, 4: 12}
TIER_LABEL = {
    0: "T0 大宗商品（<1 元/g 量级）",
    1: "T1 工业品（万元/kg 量级）",
    2: "T2 专门品（十万元/kg 量级）",
    3: "T3 稀缺品（百万元以上/kg 量级）",
    4: "T4 战略/实验品（只能按活度或原子数计）",
}

QTY_SCORE = {
    "吨级": 100, "公斤级": 82, "克级": 62, "毫克级": 44, "微克级": 26, "原子级": 8,
    "千居级": 70, "居级": 48, "毫居级": 28, "微居级": 12,
    "升级": 60, "微量": 5, "—": 5,
}

GRADES = [
    (80, "S", "随手可得"),
    (65, "A", "常规采购"),
    (50, "B", "需专门渠道"),
    (35, "C", "稀缺/受限"),
    (20, "D", "实验室级别"),
    (0, "E", "仅少数机构可产"),
]


def _isnan(x) -> bool:
    try:
        return x != x
    except Exception:  # noqa: BLE001
        return False


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def abundance_score(frac: float | None) -> float:
    """天然丰度 -> 0..100（对数刻度）。人工核素丰度为 0 或缺失时得 0 分。"""
    if frac is None or _isnan(frac) or frac <= 0:
        return 0.0
    if frac >= 1.0:
        return 100.0
    return clamp(100.0 + 12.5 * math.log10(frac))


def method_from_text(text: str) -> str:
    """从"天然｜低温蒸馏/气体离心"这类描述里取出最省事的一种工艺。"""
    if not text:
        return "无需富集"
    best, best_key = -1.0, "无需富集"
    for key, canon in METHOD_ALIAS:
        if key in text:
            sc = METHOD_SCORE[canon][0]
            if sc > best:
                best, best_key = sc, canon
    return best_key


def method_from_route(route: str, nuclide: str | None = None) -> str | None:
    """放射性核素按生产路线定类；稳定核素返回 None（改用元素级默认）。

    判定顺序：先看有没有同位素富集工艺（有就按它），再看是不是天然直接可得。
    `nuclide` 仅用于区分「加速器合成（常规）」与「加速器合成」。
    """
    r = route or ""
    enrich_classes = ("气体离心", "低温蒸馏", "化学交换", "离子交换色谱",
                      "热扩散", "电磁分离", "激光分离")
    best: str | None = None
    for key, canon in METHOD_ALIAS:
        if key in r and canon in enrich_classes:
            if best is None or METHOD_SCORE[canon][0] > METHOD_SCORE[best][0]:
                best = canon
    if best:
        return best
    if any(k in r for k in ("散裂",)):
        return "散裂/放射性束"
    if any(k in r for k in ("加速器", "回旋加速器")):
        if nuclide and nuclide in ACCEL_ROUTINE:
            return "加速器合成（常规）"
        return "加速器合成"
    if any(k in r for k in ("发生器",)):
        return "发生器洗脱"
    if any(k in r for k in ("裂变", "乏燃料")):
        return "裂变产物分离"
    if any(k in r for k in ("反应堆", "(n,γ)", "(n,p)", "(n,α)", "(n,2n)")):
        return "反应堆活化"
    if "天然" in r or "单同位素" in r:
        return "无需富集"
    return None


def quantity_score(qty: str) -> float:
    return QTY_SCORE.get(qty, 30.0)


def supply_score(qty: str, tier: int) -> float:
    base = {
        "吨级": 95, "公斤级": 85, "克级": 70, "毫克级": 55, "微克级": 38, "原子级": 15,
        "升级": 75, "千居级": 70, "居级": 55, "毫居级": 50, "微居级": 25,
        "微量": 20, "—": 20,
    }.get(qty, 40)
    return clamp(base - (tier * 3))


def regulatory_score(z: int, frac: float | None, tier: int) -> float:
    """管制负担分（越高越省事）。"""
    if z >= 84:                      # 天然放射性元素
        if z in (92, 93, 94) or (z == 92):
            return 12                # 铀/镎/钚：保障监督
        if z in (95, 96):
            return 20
        if z in (84, 85, 87, 88):
            return 28
        return 35
    if z == 43 or z == 61:           # 锝/钷
        return 45
    if frac is not None and not _isnan(frac):   # 稳定或原生放射性核素
        return 90
    return 65 if tier <= 2 else 55   # 人工放射性核素


def grade_of(score: float) -> tuple[str, str]:
    for lo, g, label in GRADES:
        if score >= lo:
            return g, label
    return "E", "基本不可得"


GATE_DIMS = ("A2", "A3", "A4", "A5", "A6", "A7")


def composite(subs: dict[str, float]) -> float:
    """加权平均 × 短板折损。

    短板只在 A2–A7 上取：A1（天然丰度）是“白送的福利分”，不是工程瓶颈——
    人工核素的丰度天然为 0，其真正的门槛已经体现在 A2（必须合成）上。
    """
    base = sum(w * subs[k] for k, _, w in WEIGHTS)
    worst = min(subs[k] for k in GATE_DIMS)
    return round(clamp(base * (0.60 + 0.40 * worst / 100.0)), 1)


def regen_class(route: str, stable: bool) -> str:
    """衰变/消耗后能否"回炉"再生（TUIA 的一个观察维度）。"""
    if stable:
        return "不衰变（无需再生）"
    r = route or ""
    if any(k in r for k in ("发生器", "衰变链")):
        return "衰变链再生（发生器中连续洗脱）"
    if any(k in r for k in ("裂变", "乏燃料")):
        return "裂变副产（随乏燃料持续产出）"
    if "(n,γ)" in r or "反应堆" in r or "(n,p)" in r:
        return "反应堆再生（靶材可重复辐照）"
    if "加速器" in r:
        return "加速器单程（需重复照射）"
    return "单程（不可再生）"
