class RankingService:
    @staticmethod
    def rank_skills_by_importance(skills_or_pairs):
        if not skills_or_pairs:
            return []
        
        # Определяем тип первого элемента
        first_type = type(skills_or_pairs[0])

        # Проверяем, что все элементы одного типа
        if not all(type(item) is first_type for item in skills_or_pairs):
            raise ValueError("Список не должен смешивать кортежи и другие типы. Либо только кортежи (skill, importance), либо только строки.")
        if first_type is tuple:
            # Проверка формата каждого кортежа
            valid = []
            for item in skills_or_pairs:
                if len(item) != 2 or not isinstance(item[1], (int, float)):
                    raise ValueError(f"Каждый кортеж должен быть вида (skill: str, importance: number). Получено: {item}")
                valid.append(item)

            # Сортируем по важности
            sorted_pairs = sorted(skills_or_pairs, key=lambda x: x[1], reverse=True)
            return [skill for skill, _ in sorted_pairs]
        else:
            return list(skills_or_pairs)
