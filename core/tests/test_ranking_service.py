import pytest
from core.models import Skill
from core.services.ranking_service import RankingService


@pytest.fixture
def skills_with_importance():
    s1 = Skill(id=1, name='C++')
    s2 = Skill(id=2, name='Python')
    s3 = Skill(id=3, name='Django')
    return [(s1, 5), (s2, 10), (s3, 7)]

def test_rank_skills_by_importance(skills_with_importance):
    ranked = RankingService.rank_skills_by_importance(skills_with_importance)
    assert ranked[0].name == 'Python'
    assert ranked[1].name == 'Django'
    assert ranked[2].name == 'C++'
    