from .base import BaseBenchmark


class BenchmarkRegistry:
    _benchmarks: dict[str, type[BaseBenchmark]] = {}

    @classmethod
    def register(cls, name: str) -> callable:
        def decorator(benchmark_class: type[BaseBenchmark]) -> type[BaseBenchmark]:
            cls._benchmarks[name] = benchmark_class
            return benchmark_class

        return decorator

    @classmethod
    def get(cls, name: str) -> type[BaseBenchmark]:
        if name not in cls._benchmarks:
            raise ValueError(f"Unknown benchmark: {name}")
        return cls._benchmarks[name]

    @classmethod
    def list(cls) -> list[str]:
        return list(cls._benchmarks.keys())

    @classmethod
    def get_info(cls, name: str) -> dict:
        benchmark_class = cls.get(name)
        return {
            "name": benchmark_class.name,
            "description": benchmark_class.description,
            "category": benchmark_class.category,
            "num_samples": benchmark_class.num_samples,
        }
