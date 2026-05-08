import pytest
from core.services.ranking_service import RankingService


class TestRankingService:
    def test_empty_list(self):
        """Пустой список возвращает пустой список."""
        assert RankingService.rank_skills_by_importance([]) == []

    def test_list_of_strings(self):
        """Список строк возвращается без изменений."""
        skills = ["Python", "Django", "SQL"]
        result = RankingService.rank_skills_by_importance(skills)
        assert result == skills

    def test_list_of_tuples_sorted_by_importance_desc(self):
        """Кортежи (skill, importance) сортируются по убыванию importance."""
        pairs = [
            ("Python", 10),
            ("Django", 5),
            ("SQL", 8),
            ("Docker", 1),
        ]
        expected = ["Python", "SQL", "Django", "Docker"]
        result = RankingService.rank_skills_by_importance(pairs)
        assert result == expected

    def test_tuples_equal_importance_preserves_order(self):
        """При равной важности порядок сохраняется (стабильная сортировка)."""
        pairs = [("A", 5), ("B", 5), ("C", 5)]
        result = RankingService.rank_skills_by_importance(pairs)
        assert result == ["A", "B", "C"]

    def test_mixed_types_raises_value_error(self):
        """Смешивание строк и кортежей вызывает ValueError."""
        mixed = ["Python", ("Django", 10)]
        with pytest.raises(ValueError, match="Список не должен смешивать кортежи и другие типы"):
            RankingService.rank_skills_by_importance(mixed)

    def test_invalid_tuple_length_raises_value_error(self):
        """Кортеж длиной не 2 вызывает ошибку."""
        invalid = [("Python", 10, "extra")]
        with pytest.raises(ValueError, match="Каждый кортеж должен быть вида \\(skill: str, importance: number\\)"):
            RankingService.rank_skills_by_importance(invalid)

    def test_tuple_second_element_not_number_raises_value_error(self):
        """Второй элемент кортежа должен быть числом (int или float)."""
        invalid = [("Python", "high")]
        with pytest.raises(ValueError, match="Каждый кортеж должен быть вида \\(skill: str, importance: number\\)"):
            RankingService.rank_skills_by_importance(invalid)

    def test_empty_tuple_in_list_raises_value_error(self):
        """Пустой кортеж также недопустим."""
        invalid = [()]
        with pytest.raises(ValueError, match="Каждый кортеж должен быть вида"):
            RankingService.rank_skills_by_importance(invalid)

    def test_single_tuple(self):
        """Одиночный кортеж корректно обрабатывается."""
        pairs = [("Python", 100)]
        result = RankingService.rank_skills_by_importance(pairs)
        assert result == ["Python"]

    def test_single_string(self):
        """Одиночная строка возвращается как есть."""
        result = RankingService.rank_skills_by_importance(["Python"])
        assert result == ["Python"]
        