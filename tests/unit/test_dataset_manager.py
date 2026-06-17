import pytest

from src.domain.datasets.dataset_manager import DatasetManager


class TestDatasetManager:
    def setup_method(self):
        self.manager = DatasetManager()

    def test_create_dataset(self):
        dataset = self.manager.create_dataset(
            name="Test Dataset",
            description="Test description",
            category="test",
        )
        assert dataset.id is not None
        assert dataset.name == "Test Dataset"
        assert dataset.category == "test"

    def test_get_dataset(self):
        dataset = self.manager.create_dataset(
            name="Test Dataset",
            description="Test description",
            category="test",
        )
        retrieved = self.manager.get_dataset(dataset.id)
        assert retrieved is not None
        assert retrieved.name == "Test Dataset"

    def test_list_datasets(self):
        self.manager.create_dataset(name="Dataset 1", description="", category="test")
        self.manager.create_dataset(name="Dataset 2", description="", category="test")
        datasets = self.manager.list_datasets()
        assert len(datasets) == 2

    def test_delete_dataset(self):
        dataset = self.manager.create_dataset(
            name="Test Dataset",
            description="Test description",
            category="test",
        )
        result = self.manager.delete_dataset(dataset.id)
        assert result is True
        assert self.manager.get_dataset(dataset.id) is None

    def test_create_version(self):
        dataset = self.manager.create_dataset(
            name="Test Dataset",
            description="Test description",
            category="test",
        )
        samples = [
            {"question": "What is 2+2?", "choices": ["A. 3", "B. 4"], "answer": "B"},
            {"question": "What is 3+3?", "choices": ["A. 5", "B. 6"], "answer": "B"},
        ]
        version = self.manager.create_version(dataset.id, samples, "Initial version")
        assert version is not None
        assert version.version_number == "v1"
        assert len(version.samples) == 2
        assert version.is_active is True

    def test_get_version(self):
        dataset = self.manager.create_dataset(
            name="Test Dataset",
            description="Test description",
            category="test",
        )
        samples = [{"question": "Test", "answer": "A"}]
        version = self.manager.create_version(dataset.id, samples)
        retrieved = self.manager.get_version(dataset.id, version.version_id)
        assert retrieved is not None
        assert retrieved.version_id == version.version_id

    def test_get_active_version(self):
        dataset = self.manager.create_dataset(
            name="Test Dataset",
            description="Test description",
            category="test",
        )
        samples = [{"question": "Test", "answer": "A"}]
        self.manager.create_version(dataset.id, samples)
        active = self.manager.get_active_version(dataset.id)
        assert active is not None
        assert active.is_active is True

    def test_multiple_versions(self):
        dataset = self.manager.create_dataset(
            name="Test Dataset",
            description="Test description",
            category="test",
        )
        self.manager.create_version(dataset.id, [{"question": "Test1", "answer": "A"}])
        self.manager.create_version(dataset.id, [{"question": "Test2", "answer": "B"}])

        assert len(dataset.versions) == 2
        assert dataset.versions[0].is_active is False
        assert dataset.versions[1].is_active is True
        assert dataset.latest_version.version_number == "v2"

    def test_add_samples(self):
        dataset = self.manager.create_dataset(
            name="Test Dataset",
            description="Test description",
            category="test",
        )
        self.manager.create_version(dataset.id, [{"question": "Test1", "answer": "A"}])

        added = self.manager.add_samples(dataset.id, [
            {"question": "Test2", "answer": "B"},
            {"question": "Test3", "answer": "C"},
        ])

        assert len(added) == 2
        assert len(dataset.latest_version.samples) == 3

    def test_remove_sample(self):
        dataset = self.manager.create_dataset(
            name="Test Dataset",
            description="Test description",
            category="test",
        )
        samples = [
            {"id": "sample-1", "question": "Test1", "answer": "A"},
            {"id": "sample-2", "question": "Test2", "answer": "B"},
        ]
        self.manager.create_version(dataset.id, samples)

        result = self.manager.remove_sample(dataset.id, "sample-1")
        assert result is True
        assert len(dataset.latest_version.samples) == 1

    def test_get_sample(self):
        dataset = self.manager.create_dataset(
            name="Test Dataset",
            description="Test description",
            category="test",
        )
        samples = [{"id": "sample-1", "question": "Test", "answer": "A"}]
        self.manager.create_version(dataset.id, samples)

        sample = self.manager.get_sample("sample-1")
        assert sample is not None
        assert sample.id == "sample-1"

    def test_recycle_failed_samples(self):
        dataset = self.manager.create_dataset(
            name="Test Dataset",
            description="Test description",
            category="test",
        )
        samples = [
            {"id": "sample-1", "question": "Test1", "answer": "A"},
            {"id": "sample-2", "question": "Test2", "answer": "B"},
        ]
        self.manager.create_version(dataset.id, samples)

        recycled = self.manager.recycle_failed_samples(dataset.id, ["sample-1"])
        assert len(recycled) == 1
        assert recycled[0].metadata.get("recycled") is True

    def test_search_samples(self):
        dataset = self.manager.create_dataset(
            name="Test Dataset",
            description="Test description",
            category="test",
        )
        samples = [
            {"question": "What is Python?", "answer": "A"},
            {"question": "What is Java?", "answer": "B"},
            {"question": "Python features", "answer": "C"},
        ]
        self.manager.create_version(dataset.id, samples)

        results = self.manager.search_samples(dataset.id, "Python")
        assert len(results) == 2

    def test_get_dataset_stats(self):
        dataset = self.manager.create_dataset(
            name="Test Dataset",
            description="Test description",
            category="test",
        )
        samples = [
            {"question": "Test1", "answer": "A"},
            {"question": "Test2", "answer": "B"},
            {"question": "Test3"},
        ]
        self.manager.create_version(dataset.id, samples)

        stats = self.manager.get_dataset_stats(dataset.id)
        assert stats is not None
        assert stats["total_samples"] == 3
        assert stats["samples_with_answer"] == 2
        assert stats["samples_without_answer"] == 1

    def test_dataset_to_dict(self):
        dataset = self.manager.create_dataset(
            name="Test Dataset",
            description="Test description",
            category="test",
        )
        samples = [{"question": "Test", "answer": "A"}]
        self.manager.create_version(dataset.id, samples)

        data = dataset.to_dict()
        assert data["id"] == dataset.id
        assert data["name"] == "Test Dataset"
        assert "version_count" in data
        assert "latest_version" in data
