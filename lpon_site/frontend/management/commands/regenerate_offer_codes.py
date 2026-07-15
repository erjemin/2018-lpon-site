"""
Django management команда для перегенерации и проверки s_offer_code офферов.

ВАЖНО: При смене OFFER_HASHIDS_SALT нужно обновить ВСЕ коды сразу!
Иначе старые коды перестанут работать и QR-коды станут невалидными.

Примеры использования:
    # 1. Проверить все коды (декодирование и валидация)
    python manage.py regenerate_offer_codes --check

    # 2. Проверить и показать некорректные коды
    python manage.py regenerate_offer_codes --check --verbose

    # 3. Обновить только некорректные коды
    python manage.py regenerate_offer_codes --fix-broken

    # 4. Обновить ВСЕ коды (при смене соли)
    python manage.py regenerate_offer_codes

    # 5. Пробный запуск (ничего не сохранять)
    python manage.py regenerate_offer_codes --dry-run
"""

from django.core.management.base import BaseCommand, CommandError
from hashids import Hashids
from lpon_site.settings import OFFER_HASHIDS_SALT, OFFER_HASHIDS_MIN_LENGTH
from frontend.models import TbOffer


class Command(BaseCommand):
    """
    Перегенерирует, проверяет и восстанавливает s_offer_code офферов.
    """
    help = 'Перегенерирует/проверяет s_offer_code для офферов на основе текущего OFFER_HASHIDS_SALT'

    def add_arguments(self, parser):
        """Добавляем опциональные аргументы"""
        parser.add_argument(
            '--check',
            action='store_true',
            help='Проверить корректность всех кодов (декодировать обратно в id)',
        )

        parser.add_argument(
            '--fix-broken',
            action='store_true',
            help='Обновить только коды, которые не декодируются правильно',
        )

        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет изменено, но не сохранять',
        )

        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Показывать подробный прогресс для каждого оффера',
        )

    def handle(self, *args, **options):
        """Основная логика команды"""
        check_mode = options['check']
        fix_broken = options['fix_broken']
        dry_run = options['dry_run']
        verbose = options['verbose']

        # Инициализируем Hashids
        hashids = Hashids(salt=OFFER_HASHIDS_SALT, min_length=OFFER_HASHIDS_MIN_LENGTH)

        # Получаем все офферы
        queryset = TbOffer.objects.all()
        total_count = queryset.count()

        if total_count == 0:
            self.stdout.write(self.style.WARNING('Нет офферов для обработки'))
            return

        self.stdout.write(
            self.style.SUCCESS(f'Найдено офферов: {total_count}')
        )

        # ===== РЕЖИМ 1: ПРОВЕРКА КОДОВ =====
        if check_mode:
            self._check_codes(queryset, hashids, verbose, total_count)
            return

        # ===== РЕЖИМ 2: ОБНОВЛЕНИЕ ТОЛЬКО НЕКОРРЕКТНЫХ =====
        if fix_broken:
            self._fix_broken_codes(queryset, hashids, dry_run, verbose, total_count)
            return

        # ===== РЕЖИМ 3: ОБНОВЛЕНИЕ ВСЕХ КОДОВ =====
        self._regenerate_all_codes(queryset, hashids, dry_run, verbose, total_count)

    def _check_codes(self, queryset, hashids, verbose, total_count):
        """
        Режим проверки: декодируем все коды обратно и проверяем, что получается исходный id.
        """
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('РЕЖИМ ПРОВЕРКИ КОДОВ'))
        self.stdout.write('=' * 70)

        broken_count = 0
        valid_count = 0
        broken_offers = []

        for idx, offer in enumerate(queryset.iterator(chunk_size=1000), 1):
            try:
                # Пытаемся декодировать код обратно в ID
                decoded_ids = hashids.decode(offer.s_offer_code)

                if not decoded_ids or decoded_ids[0] != offer.id:
                    # Код не декодируется или декодируется в неправильный ID
                    broken_count += 1
                    broken_offers.append({
                        'id': offer.id,
                        'code': offer.s_offer_code,
                        'decoded': decoded_ids[0] if decoded_ids else None,
                        'reason': 'Неверный ID' if decoded_ids else 'Не декодируется'
                    })

                    if verbose:
                        self.stdout.write(
                            self.style.ERROR(
                                f'  [{idx}/{total_count}] ID={offer.id} [err] код "{offer.s_offer_code}" '
                                f'декодируется в {decoded_ids[0] if decoded_ids else "ОШИБКА"}'
                            )
                        )
                else:
                    # Код корректный
                    valid_count += 1
                    if verbose:
                        self.stdout.write(
                            f'  [{idx}/{total_count}] ID={offer.id} [ok!] код "{offer.s_offer_code}"'
                        )

            except Exception as e:
                broken_count += 1
                broken_offers.append({
                    'id': offer.id,
                    'code': offer.s_offer_code,
                    'error': str(e)
                })
                if verbose:
                    self.stdout.write(
                        self.style.ERROR(
                            f'  [{idx}/{total_count}] ID={offer.id} [err] код "{offer.s_offer_code}" ОШИБКА: {str(e)}'
                        )
                    )

            # Показываем прогресс каждые 1000
            if idx % 1000 == 0:
                self.stdout.write(f'Проверено: {idx}/{total_count}')

        # Отчет
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('ИТОГОВЫЙ ОТЧЕТ ПРОВЕРКИ'))
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS(f'[ok!] Корректных кодов: {valid_count}'))

        if broken_count > 0:
            self.stdout.write(self.style.ERROR(f'[err] Некорректных кодов: {broken_count}'))
            
            if broken_count <= 20:
                # Показываем все если мало
                self.stdout.write('\nДетали некорректных кодов:')
                for item in broken_offers:
                    if 'error' in item:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ID={item['id']}, код='{item['code']}', ошибка: {item['error']}"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ID={item['id']}, код='{item['code']}', "
                                f"декодируется в {item['decoded']}, причина: {item['reason']}"
                            )
                        )
            else:
                self.stdout.write(f'\nПервые 20 некорректных кодов:')
                for item in broken_offers[:20]:
                    if 'error' in item:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ID={item['id']}, код='{item['code']}', ошибка: {item['error']}"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ID={item['id']}, код='{item['code']}', "
                                f"декодируется в {item['decoded']}, причина: {item['reason']}"
                            )
                        )
        else:
            self.stdout.write(self.style.SUCCESS('Все коды корректны! [ok!]'))

        self.stdout.write(f'\nОбщее количество: {valid_count + broken_count}')
        self.stdout.write(
            self.style.WARNING(
                '\nДля обновления некорректных кодов используйте: '
                '--fix-broken'
            )
        )

    def _fix_broken_codes(self, queryset, hashids, dry_run, verbose, total_count):
        """
        Режим исправления: обновляем только те коды которые не декодируются правильно.
        """
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('РЕЖИМ ИСПРАВЛЕНИЯ НЕКОРРЕКТНЫХ КОДОВ'))
        self.stdout.write('=' * 70)

        updated = 0
        skipped = 0
        failed = 0

        if dry_run:
            self.stdout.write(self.style.WARNING('!! DRY-RUN: изменения НЕ будут сохранены !!'))

        for idx, offer in enumerate(queryset.iterator(chunk_size=1000), 1):
            try:
                # Проверяем корректность текущего кода
                decoded_ids = hashids.decode(offer.s_offer_code)

                if decoded_ids and decoded_ids[0] == offer.id:
                    # Код корректный - пропускаем
                    skipped += 1
                    if verbose:
                        self.stdout.write(f'  [{idx}/{total_count}] ID={offer.id} [ok!] пропущен (корректный)')
                    continue

                # Код некорректный - обновляем
                new_code = hashids.encode(offer.id)

                if verbose:
                    self.stdout.write(
                        f'  [{idx}/{total_count}] ID={offer.id}: '
                        f'"{offer.s_offer_code}" → "{new_code}"'
                    )

                if not dry_run:
                    # Обновляем напрямую (без вызова save() чтобы не было валидации)
                    TbOffer.objects.filter(id=offer.id).update(s_offer_code=new_code)
                    updated += 1

            except Exception as e:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'  [{idx}/{total_count}] ID={offer.id} [err] код "{offer.s_offer_code}" ОШИБКА: {str(e)}'
                    )
                )

            # Показываем прогресс каждые 1000
            if idx % 1000 == 0:
                self.stdout.write(f'Обработано: {idx}/{total_count}')

        # Отчет
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('ИТОГОВЫЙ ОТЧЕТ ИСПРАВЛЕНИЯ'))
        self.stdout.write('=' * 70)
        self.stdout.write(f'Пропущено (корректные): {skipped}')

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'Обновлено: {updated}'))
        else:
            self.stdout.write(self.style.WARNING(f'Было бы обновлено: {updated} (dry-run)'))

        if failed > 0:
            self.stdout.write(self.style.ERROR(f'Ошибок: {failed}'))
        else:
            self.stdout.write(self.style.SUCCESS('Ошибок: 0'))

        self.stdout.write(f'\nОбщее количество обработано: {skipped + updated + failed}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Изменения НЕ были сохранены (dry-run)'))

    def _regenerate_all_codes(self, queryset, hashids, dry_run, verbose, total_count):
        """
        Режим полного обновления: перегенерируем ВСЕ коды.
        ВНИМАНИЕ: Используется при смене OFFER_HASHIDS_SALT!
        """
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.ERROR('РЕЖИМ ПОЛНОГО ОБНОВЛЕНИЯ ВСЕХ КОДОВ'))
        self.stdout.write('=' * 70)
        self.stdout.write(
            self.style.WARNING(
                'ВНИМАНИЕ! Это обновит ВСЕ коды. Старые коды и QR-коды перестанут работать!\n'
                'Используется только при смене OFFER_HASHIDS_SALT на сервере.'
            )
        )

        updated = 0
        unchanged = 0
        failed = 0

        if dry_run:
            self.stdout.write(self.style.WARNING('!! DRY-RUN: изменения НЕ будут сохранены !!'))

        for idx, offer in enumerate(queryset.iterator(chunk_size=1000), 1):
            try:
                # Генерируем новый код
                new_code = hashids.encode(offer.id)

                # Проверяем изменился ли
                if offer.s_offer_code == new_code:
                    unchanged += 1
                    if verbose:
                        self.stdout.write(f'  [{idx}/{total_count}] ID={offer.id}: без изменений')
                else:
                    if verbose:
                        self.stdout.write(
                            f'  [{idx}/{total_count}] ID={offer.id}: '
                            f'"{offer.s_offer_code}" → "{new_code}"'
                        )

                    if not dry_run:
                        # Обновляем напрямую в БД
                        TbOffer.objects.filter(id=offer.id).update(s_offer_code=new_code)
                        updated += 1

            except Exception as e:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'  [{idx}/{total_count}] ID={offer.id} [err] код "{offer.s_offer_code}" ОШИБКА: {str(e)}'
                    )
                )

            # Показываем прогресс каждые 1000
            if idx % 1000 == 0:
                self.stdout.write(f'Обработано: {idx}/{total_count}')

        # Отчет
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('ИТОГОВЫЙ ОТЧЕТ ПОЛНОГО ОБНОВЛЕНИЯ'))
        self.stdout.write('=' * 70)
        self.stdout.write(f'Без изменений: {unchanged}')

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'Обновлено: {updated}'))
        else:
            self.stdout.write(self.style.WARNING(f'Было бы обновлено: {updated} (dry-run)'))

        if failed > 0:
            self.stdout.write(self.style.ERROR(f'Ошибок: {failed}'))
        else:
            self.stdout.write(self.style.SUCCESS('Ошибок: 0'))

        # Параметры
        self.stdout.write(f'\nПараметры Hashids:')
        self.stdout.write(f'  Соль: {OFFER_HASHIDS_SALT[:16]}...')
        self.stdout.write(f'  Минимальная длина: {OFFER_HASHIDS_MIN_LENGTH}')

        self.stdout.write(f'\nОбщее количество обработано: {unchanged + updated + failed}')

        if dry_run:
            self.stdout.write(self.style.WARNING('Изменения НЕ были сохранены (dry-run)'))
        else:
            self.stdout.write(self.style.SUCCESS('Команда завершена успешно! ✓'))
