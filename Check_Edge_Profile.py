# -*- coding: utf-8 -*-
"""
ПРОВЕРКА ПРОФИЛЕЙ EDGE
Показывает все доступные профили Edge и их пути
"""

import os

def main():
    print("\n" + "="*80)
    print("ПРОВЕРКА ПРОФИЛЕЙ EDGE")
    print("="*80)
    
    # Путь к User Data Edge
    edge_user_data = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")
    
    print(f"\n[1] Путь к User Data Edge:")
    print(f"    {edge_user_data}")
    
    if not os.path.exists(edge_user_data):
        print(f"\n[!] Папка не найдена! Edge может быть не установлен.")
        return
    
    print(f"\n[2] Доступные профили:")
    print("="*80)
    
    profiles_found = []
    
    # Проверяем Default профиль
    default_path = os.path.join(edge_user_data, "Default")
    if os.path.exists(default_path):
        profiles_found.append({
            'name': 'Default',
            'path': default_path,
            'is_default': True
        })
        print(f"\n✓ Default (основной профиль)")
        print(f"  Путь: {default_path}")
    
    # Ищем другие профили (Profile 1, Profile 2, и т.д.)
    if os.path.exists(edge_user_data):
        for item in os.listdir(edge_user_data):
            if item.startswith('Profile '):
                profile_path = os.path.join(edge_user_data, item)
                if os.path.isdir(profile_path):
                    profiles_found.append({
                        'name': item,
                        'path': profile_path,
                        'is_default': False
                    })
                    print(f"\n✓ {item}")
                    print(f"  Путь: {profile_path}")
    
    # Проверяем Preferences для определения активного профиля
    print(f"\n[3] Информация из Preferences:")
    print("="*80)
    
    preferences_path = os.path.join(edge_user_data, "Local State")
    if os.path.exists(preferences_path):
        try:
            import json
            with open(preferences_path, 'r', encoding='utf-8') as f:
                local_state = json.load(f)
            
            # Ищем информацию о профилях
            if 'profile' in local_state:
                profile_info = local_state['profile']
                if 'info_cache' in profile_info:
                    print(f"\nНайденные профили в Local State:")
                    for profile_name, profile_data in profile_info['info_cache'].items():
                        profile_name_display = profile_data.get('name', profile_name)
                        print(f"\n  Профиль: {profile_name}")
                        print(f"    Отображаемое имя: {profile_name_display}")
                        print(f"    Путь: {os.path.join(edge_user_data, profile_name)}")
        except Exception as e:
            print(f"  Не удалось прочитать Local State: {e}")
    
    print(f"\n[4] Рекомендации для кода:")
    print("="*80)
    
    if profiles_found:
        print(f"\nВ файле Parser_WB_Search.py используйте:")
        print(f"\nEDGE_USER_DATA_DIR = r\"{edge_user_data}\"")
        
        if len(profiles_found) == 1:
            print(f"EDGE_PROFILE_NAME = \"{profiles_found[0]['name']}\"")
        else:
            print(f"\nДоступные профили:")
            for i, profile in enumerate(profiles_found, 1):
                marker = " ← (основной)" if profile['is_default'] else ""
                print(f"  {i}. EDGE_PROFILE_NAME = \"{profile['name']}\"{marker}")
    else:
        print(f"\n[!] Профили не найдены!")
    
    print(f"\n{'='*80}")
    print("ЗАВЕРШЕНО")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()


