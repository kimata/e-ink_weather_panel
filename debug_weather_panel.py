#!/usr/bin/env python3
"""
デバッグ用のweather_panel.py修正版
空リストエラーの原因を特定するためのログとエラーハンドリングを追加
"""

import concurrent.futures
import logging
import time
import traceback

def create_weather_panel_impl_debug(panel_config, font_config, slack_config, is_side_by_side, trial, opt_config):
    """デバッグ版のweather panel作成関数"""
    logging.info("=== Weather Panel Debug Start ===")
    
    # NOTE: APIコールを並列化して高速化（デバッグ版）
    results = {}
    errors = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            'weather': executor.submit(safe_api_call, 'get_weather_yahoo', 
                                     lambda: get_weather_yahoo(panel_config["data"]["yahoo"])),
            'clothing': executor.submit(safe_api_call, 'get_clothing_yahoo',
                                      lambda: get_clothing_yahoo(panel_config["data"]["yahoo"])),
            'sunset': executor.submit(safe_api_call, 'get_sunset_nao',
                                    lambda: my_lib.weather.get_sunset_nao(opt_config["sunset"])),
            'wbgt': executor.submit(safe_api_call, 'get_wbgt',
                                  lambda: get_wbgt(opt_config["wbgt"]))
        }
        
        # 各結果を個別に処理
        for key, future in futures.items():
            try:
                start_time = time.perf_counter()
                result = future.result(timeout=30)  # 30秒タイムアウト
                end_time = time.perf_counter()
                
                if result is None:
                    logging.warning(f"API {key}: returned None")
                    results[key] = []
                elif isinstance(result, list) and len(result) == 0:
                    logging.warning(f"API {key}: returned empty list")
                    results[key] = []
                else:
                    logging.info(f"API {key}: success in {end_time-start_time:.2f}s, data length: {len(result) if isinstance(result, list) else 'not list'}")
                    results[key] = result
                    
            except concurrent.futures.TimeoutError:
                logging.error(f"API {key}: timeout after 30 seconds")
                results[key] = []
                errors[key] = "timeout"
                
            except Exception as e:
                logging.error(f"API {key}: exception: {str(e)}")
                logging.error(f"API {key}: traceback: {traceback.format_exc()}")
                results[key] = []
                errors[key] = str(e)
    
    # 結果の詳細ログ
    for key, data in results.items():
        if isinstance(data, list):
            logging.info(f"Final {key} data: length={len(data)}, sample={data[:2] if data else 'empty'}")
        else:
            logging.info(f"Final {key} data: type={type(data)}, value={str(data)[:100]}")
    
    # エラーサマリー
    if errors:
        logging.error(f"API errors occurred: {errors}")
    
    logging.info("=== Weather Panel Debug End ===")
    
    # 元の変数名で返す（互換性のため）
    return {
        'weather_info': results['weather'],
        'clothing_info': results['clothing'], 
        'sunset_info': results['sunset'],
        'wbgt_info': results['wbgt'],
        'errors': errors
    }

def safe_api_call(api_name, api_func):
    """安全なAPI呼び出しラッパー"""
    try:
        logging.info(f"Starting API call: {api_name}")
        result = api_func()
        
        # 結果の検証
        if result is None:
            logging.warning(f"{api_name}: returned None")
            return []
        elif isinstance(result, list) and len(result) == 0:
            logging.warning(f"{api_name}: returned empty list")
            return []
        elif isinstance(result, dict) and not result:
            logging.warning(f"{api_name}: returned empty dict")
            return {}
        
        logging.info(f"{api_name}: success")
        return result
        
    except Exception as e:
        logging.error(f"{api_name}: error: {str(e)}")
        logging.error(f"{api_name}: traceback: {traceback.format_exc()}")
        
        # 空のデータ構造を返す
        if 'weather' in api_name.lower():
            return []
        elif 'clothing' in api_name.lower():
            return []
        else:
            return {}

# sensor_graph.py用のデバッグ関数
def debug_sensor_data_parallel():
    """sensor_graph.pyの並列処理デバッグ"""
    logging.info("=== Sensor Data Parallel Debug ===")
    
    # 実際のfetch_data_parallel呼び出し前後にログを追加
    def fetch_data_parallel_debug(db_config, requests):
        logging.info(f"fetch_data_parallel: starting with {len(requests)} requests")
        
        start_time = time.perf_counter()
        try:
            # 元の関数を呼び出し（実装があることを前提）
            results = fetch_data_parallel(db_config, requests)
            end_time = time.perf_counter()
            
            # 結果の検証
            if not results:
                logging.error("fetch_data_parallel: returned empty results")
                return []
            
            empty_count = sum(1 for r in results if not r or (isinstance(r, dict) and not r.get('valid', False)))
            valid_count = len(results) - empty_count
            
            logging.info(f"fetch_data_parallel: completed in {end_time-start_time:.2f}s")
            logging.info(f"fetch_data_parallel: {valid_count} valid, {empty_count} empty results")
            
            return results
            
        except Exception as e:
            end_time = time.perf_counter()
            logging.error(f"fetch_data_parallel: failed after {end_time-start_time:.2f}s: {str(e)}")
            logging.error(f"fetch_data_parallel: traceback: {traceback.format_exc()}")
            return []
    
    return fetch_data_parallel_debug

if __name__ == "__main__":
    # デバッグモード用の設定
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('weather_panel_debug.log')
        ]
    )
    
    print("デバッグ用weather_panel関数を使用してテストしてください")
    print("ログは weather_panel_debug.log に出力されます")