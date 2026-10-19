"""元素基础表（Z = 1..118）。

字段说明
--------
z           原子序数
sym         元素符号
en          英文名
cn          中文名
cat         元素类别（IUPAC / 常用分类）
mono        是否天然单同位素元素（自然界只有一种同位素，丰度≈100%）
enrich      该元素同位素富集的主流工艺类别（"无（单同位素）" 表示不需要富集）
"""

from __future__ import annotations

from typing import NamedTuple


class Element(NamedTuple):
    z: int
    sym: str
    en: str
    cn: str
    cat: str
    mono: bool
    enrich: str


AM = "碱金属"
AE = "碱土金属"
TM = "过渡金属"
PTM = "后过渡金属"
ML = "类金属"
NM = "非金属"
NG = "稀有气体"
LN = "镧系"
AN = "锕系"

ELEMENTS: list[Element] = [
    Element(1, "H", "Hydrogen", "氢", NM, False, "化学交换/低温蒸馏"),
    Element(2, "He", "Helium", "氦", NG, False, "低温蒸馏"),
    Element(3, "Li", "Lithium", "锂", AM, False, "化学交换"),
    Element(4, "Be", "Beryllium", "铍", AE, True, "无（单同位素）"),
    Element(5, "B", "Boron", "硼", ML, False, "低温蒸馏/化学交换"),
    Element(6, "C", "Carbon", "碳", NM, False, "低温蒸馏/气体离心"),
    Element(7, "N", "Nitrogen", "氮", NM, False, "化学交换/低温蒸馏"),
    Element(8, "O", "Oxygen", "氧", NM, False, "低温蒸馏/热扩散"),
    Element(9, "F", "Fluorine", "氟", NM, True, "无（单同位素）"),
    Element(10, "Ne", "Neon", "氖", NG, False, "低温蒸馏"),
    Element(11, "Na", "Sodium", "钠", AM, True, "无（单同位素）"),
    Element(12, "Mg", "Magnesium", "镁", AE, False, "电磁分离/激光分离"),
    Element(13, "Al", "Aluminium", "铝", PTM, True, "无（单同位素）"),
    Element(14, "Si", "Silicon", "硅", ML, False, "气体离心"),
    Element(15, "P", "Phosphorus", "磷", NM, True, "无（单同位素）"),
    Element(16, "S", "Sulfur", "硫", NM, False, "气体离心/低温蒸馏"),
    Element(17, "Cl", "Chlorine", "氯", NM, False, "气体离心"),
    Element(18, "Ar", "Argon", "氩", NG, False, "低温蒸馏"),
    Element(19, "K", "Potassium", "钾", AM, False, "电磁分离/激光分离"),
    Element(20, "Ca", "Calcium", "钙", AE, False, "电磁分离/激光分离"),
    Element(21, "Sc", "Scandium", "钪", TM, True, "无（单同位素）"),
    Element(22, "Ti", "Titanium", "钛", TM, False, "气体离心"),
    Element(23, "V", "Vanadium", "钒", TM, False, "气体离心/电磁分离"),
    Element(24, "Cr", "Chromium", "铬", TM, False, "气体离心"),
    Element(25, "Mn", "Manganese", "锰", TM, True, "无（单同位素）"),
    Element(26, "Fe", "Iron", "铁", TM, False, "气体离心"),
    Element(27, "Co", "Cobalt", "钴", TM, True, "无（单同位素）"),
    Element(28, "Ni", "Nickel", "镍", TM, False, "气体离心"),
    Element(29, "Cu", "Copper", "铜", TM, False, "气体离心/电磁分离"),
    Element(30, "Zn", "Zinc", "锌", TM, False, "离子交换色谱"),
    Element(31, "Ga", "Gallium", "镓", PTM, False, "电磁分离/气体离心"),
    Element(32, "Ge", "Germanium", "锗", ML, False, "气体离心"),
    Element(33, "As", "Arsenic", "砷", ML, True, "无（单同位素）"),
    Element(34, "Se", "Selenium", "硒", NM, False, "气体离心"),
    Element(35, "Br", "Bromine", "溴", NM, False, "化学交换/气体离心"),
    Element(36, "Kr", "Krypton", "氪", NG, False, "低温蒸馏"),
    Element(37, "Rb", "Rubidium", "铷", AM, False, "离子交换色谱/激光分离"),
    Element(38, "Sr", "Strontium", "锶", AE, False, "离子交换色谱/激光分离"),
    Element(39, "Y", "Yttrium", "钇", TM, True, "无（单同位素）"),
    Element(40, "Zr", "Zirconium", "锆", TM, False, "气体离心"),
    Element(41, "Nb", "Niobium", "铌", TM, True, "无（单同位素）"),
    Element(42, "Mo", "Molybdenum", "钼", TM, False, "气体离心/离子交换色谱"),
    Element(43, "Tc", "Technetium", "锝", TM, False, "裂变产物分离"),
    Element(44, "Ru", "Ruthenium", "钌", TM, False, "离子交换色谱/低温蒸馏"),
    Element(45, "Rh", "Rhodium", "铑", TM, True, "无（单同位素）"),
    Element(46, "Pd", "Palladium", "钯", TM, False, "离子交换色谱"),
    Element(47, "Ag", "Silver", "银", TM, False, "电磁分离"),
    Element(48, "Cd", "Cadmium", "镉", TM, False, "离子交换色谱/激光分离"),
    Element(49, "In", "Indium", "铟", PTM, False, "电磁分离"),
    Element(50, "Sn", "Tin", "锡", PTM, False, "气体离心"),
    Element(51, "Sb", "Antimony", "锑", ML, False, "电磁分离"),
    Element(52, "Te", "Tellurium", "碲", ML, False, "气体离心"),
    Element(53, "I", "Iodine", "碘", NM, True, "无（单同位素）"),
    Element(54, "Xe", "Xenon", "氙", NG, False, "低温蒸馏"),
    Element(55, "Cs", "Caesium", "铯", AM, True, "无（单同位素）"),
    Element(56, "Ba", "Barium", "钡", AE, False, "离子交换色谱/激光分离"),
    Element(57, "La", "Lanthanum", "镧", LN, False, "离子交换色谱"),
    Element(58, "Ce", "Cerium", "铈", LN, False, "离子交换色谱/电磁分离"),
    Element(59, "Pr", "Praseodymium", "镨", LN, True, "无（单同位素）"),
    Element(60, "Nd", "Neodymium", "钕", LN, False, "离子交换色谱"),
    Element(61, "Pm", "Promethium", "钷", LN, False, "裂变产物分离"),
    Element(62, "Sm", "Samarium", "钐", LN, False, "离子交换色谱/电磁分离"),
    Element(63, "Eu", "Europium", "铕", LN, False, "离子交换色谱/电磁分离"),
    Element(64, "Gd", "Gadolinium", "钆", LN, False, "离子交换色谱"),
    Element(65, "Tb", "Terbium", "铽", LN, True, "无（单同位素）"),
    Element(66, "Dy", "Dysprosium", "镝", LN, False, "离子交换色谱"),
    Element(67, "Ho", "Holmium", "钬", LN, True, "无（单同位素）"),
    Element(68, "Er", "Erbium", "铒", LN, False, "离子交换色谱/电磁分离"),
    Element(69, "Tm", "Thulium", "铥", LN, True, "无（单同位素）"),
    Element(70, "Yb", "Ytterbium", "镱", LN, False, "电磁分离/激光分离"),
    Element(71, "Lu", "Lutetium", "镥", LN, False, "离子交换色谱/电磁分离"),
    Element(72, "Hf", "Hafnium", "铪", TM, False, "气体离心"),
    Element(73, "Ta", "Tantalum", "钽", TM, False, "电磁分离"),
    Element(74, "W", "Tungsten", "钨", TM, False, "气体离心"),
    Element(75, "Re", "Rhenium", "铼", TM, False, "电磁分离"),
    Element(76, "Os", "Osmium", "锇", TM, False, "离子交换色谱/电磁分离"),
    Element(77, "Ir", "Iridium", "铱", TM, False, "电磁分离"),
    Element(78, "Pt", "Platinum", "铂", TM, False, "离子交换色谱/电磁分离"),
    Element(79, "Au", "Gold", "金", TM, True, "无（单同位素）"),
    Element(80, "Hg", "Mercury", "汞", TM, False, "电磁分离/激光分离"),
    Element(81, "Tl", "Thallium", "铊", PTM, False, "电磁分离"),
    Element(82, "Pb", "Lead", "铅", PTM, False, "电磁分离/激光分离"),
    Element(83, "Bi", "Bismuth", "铋", PTM, True, "无（单同位素）"),
    Element(84, "Po", "Polonium", "钋", PTM, False, "反应堆活化"),
    Element(85, "At", "Astatine", "砹", ML, False, "加速器合成"),
    Element(86, "Rn", "Radon", "氡", NG, False, "发生器洗脱"),
    Element(87, "Fr", "Francium", "钫", AM, False, "加速器合成"),
    Element(88, "Ra", "Radium", "镭", AE, False, "裂变产物分离/发生器洗脱"),
    Element(89, "Ac", "Actinium", "锕", AN, False, "反应堆活化/加速器合成"),
    Element(90, "Th", "Thorium", "钍", AN, True, "无（单同位素）"),
    Element(91, "Pa", "Protactinium", "镤", AN, False, "反应堆活化/加速器合成"),
    Element(92, "U", "Uranium", "铀", AN, False, "气体离心"),
    Element(93, "Np", "Neptunium", "镎", AN, False, "反应堆活化"),
    Element(94, "Pu", "Plutonium", "钚", AN, False, "反应堆活化/后处理"),
    Element(95, "Am", "Americium", "镅", AN, False, "反应堆活化"),
    Element(96, "Cm", "Curium", "锔", AN, False, "反应堆活化/加速器合成"),
    Element(97, "Bk", "Berkelium", "锫", AN, False, "加速器合成"),
    Element(98, "Cf", "Californium", "锎", AN, False, "反应堆活化/加速器合成"),
    Element(99, "Es", "Einsteinium", "锿", AN, False, "加速器合成"),
    Element(100, "Fm", "Fermium", "镄", AN, False, "加速器合成"),
    Element(101, "Md", "Mendelevium", "钔", AN, False, "加速器合成"),
    Element(102, "No", "Nobelium", "锘", AN, False, "加速器合成"),
    Element(103, "Lr", "Lawrencium", "铹", AN, False, "加速器合成"),
    Element(104, "Rf", "Rutherfordium", "𬬻", TM, False, "加速器合成"),
    Element(105, "Db", "Dubnium", "𬭊", TM, False, "加速器合成"),
    Element(106, "Sg", "Seaborgium", "𬭳", TM, False, "加速器合成"),
    Element(107, "Bh", "Bohrium", "𬭛", TM, False, "加速器合成"),
    Element(108, "Hs", "Hassium", "𬭶", TM, False, "加速器合成"),
    Element(109, "Mt", "Meitnerium", "鿏", TM, False, "加速器合成"),
    Element(110, "Ds", "Darmstadtium", "𫟼", TM, False, "加速器合成"),
    Element(111, "Rg", "Roentgenium", "𬬭", TM, False, "加速器合成"),
    Element(112, "Cn", "Copernicium", "鿔", TM, False, "加速器合成"),
    Element(113, "Nh", "Nihonium", "鿭", PTM, False, "加速器合成"),
    Element(114, "Fl", "Flerovium", "𫓧", PTM, False, "加速器合成"),
    Element(115, "Mc", "Moscovium", "镆", PTM, False, "加速器合成"),
    Element(116, "Lv", "Livermorium", "𫟷", PTM, False, "加速器合成"),
    Element(117, "Ts", "Tennessine", "鿬", ML, False, "加速器合成"),
    Element(118, "Og", "Oganesson", "鿫", NG, False, "加速器合成"),
]

BY_Z: dict[int, Element] = {e.z: e for e in ELEMENTS}
BY_SYM: dict[str, Element] = {e.sym: e for e in ELEMENTS}

assert len(ELEMENTS) == 118 and [e.z for e in ELEMENTS] == list(range(1, 119))

# 周期表版式（周衍图用）：(Z, 列, 行)
# 列 1..18；镧系/锕系按常规放到下方两行
_MAIN = {
    1: (1, 1), 2: (18, 1),
    3: (1, 2), 4: (2, 2), 5: (13, 2), 6: (14, 2), 7: (15, 2), 8: (16, 2), 9: (17, 2), 10: (18, 2),
    11: (1, 3), 12: (2, 3), 13: (13, 3), 14: (14, 3), 15: (15, 3), 16: (16, 3), 17: (17, 3), 18: (18, 3),
    19: (1, 4), 20: (2, 4), 21: (3, 4), 22: (4, 4), 23: (5, 4), 24: (6, 4), 25: (7, 4), 26: (8, 4),
    27: (9, 4), 28: (10, 4), 29: (11, 4), 30: (12, 4), 31: (13, 4), 32: (14, 4), 33: (15, 4),
    34: (16, 4), 35: (17, 4), 36: (18, 4),
    37: (1, 5), 38: (2, 5), 39: (3, 5), 40: (4, 5), 41: (5, 5), 42: (6, 5), 43: (7, 5), 44: (8, 5),
    45: (9, 5), 46: (10, 5), 47: (11, 5), 48: (12, 5), 49: (13, 5), 50: (14, 5), 51: (15, 5),
    52: (16, 5), 53: (17, 5), 54: (18, 5),
    55: (1, 6), 56: (2, 6), 72: (4, 6), 73: (5, 6), 74: (6, 6), 75: (7, 6), 76: (8, 6), 77: (9, 6),
    78: (10, 6), 79: (11, 6), 80: (12, 6), 81: (13, 6), 82: (14, 6), 83: (15, 6), 84: (16, 6),
    85: (17, 6), 86: (18, 6),
    87: (1, 7), 88: (2, 7), 104: (4, 7), 105: (5, 7), 106: (6, 7), 107: (7, 7), 108: (8, 7),
    109: (9, 7), 110: (10, 7), 111: (11, 7), 112: (12, 7), 113: (13, 7), 114: (14, 7),
    115: (15, 7), 116: (16, 7), 117: (17, 7), 118: (18, 7),
}
# 镧系 57-71 → 第 9 行（列 3..17）；锕系 89-103 → 第 10 行（列 3..17）
for _i, _z in enumerate(range(57, 72)):
    _MAIN[_z] = (3 + _i, 9)
for _i, _z in enumerate(range(89, 104)):
    _MAIN[_z] = (3 + _i, 10)

GRID: dict[int, tuple[int, int]] = _MAIN
