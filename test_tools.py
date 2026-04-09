import parser
import rule_generator

def test_parser():
    print("Testing parser.py...")
    res1 = parser.parse_tenhou_tile(128) # dora indicator flag is 0x80 (128)
    print(res1)
    res2 = parser.parse_tenhou_tile(132) # dora ind + some base tile (128 + 4 = 5m?)
    print(res2)
    res3 = parser.parse_tenhou_tile(5)
    print(res3)
    res4 = parser.parse_tenhou_tile(31)
    print(res4)

def test_rule_generator():
    print("Testing rule_generator.py...")
    gen = rule_generator.StatisticalRuleGenerator()
    res = gen.analyze_pattern([], "test_pattern")
    print(f"Status: {res.status}, Sample Size: {res.sample_size}, Disclaimer: {res.disclaimer}")
    rule = gen.generate_rule(res, "test_pattern")
    print("Rule:", rule)

if __name__ == "__main__":
    test_parser()
    test_rule_generator()
