
TEST_MODULES = [
    'test_delta_simple9',
    'test_delta_simple9_bench',
    'test_tsdb_core',
]

def main():
    for module_name in TEST_MODULES:
        mod = __import__(module_name)
        print(module_name)
        mod.main()

if __name__ == "__main__":
    main()
