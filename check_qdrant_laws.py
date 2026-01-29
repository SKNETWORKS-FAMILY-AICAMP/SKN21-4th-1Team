"""
Qdrant DB에 저장된 법령 문서 분석 스크립트
노동법 vs 노동법 외 법령 분포 확인
"""
import os
import django
from collections import Counter

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from qdrant_client import QdrantClient
from chat.ai_module.config import Config

def analyze_qdrant_laws():
    """Qdrant collection의 법령 분포 분석"""
    
    config = Config()
    
    # Qdrant 클라이언트 연결
    client = QdrantClient(
        url=config.QDRANT_URL,
        api_key=config.QDRANT_API_KEY,
        timeout=config.QDRANT_TIMEOUT
    )
    
    collection_name = config.QDRANT_COLLECTION_NAME
    
    print(f"📊 Qdrant Collection 분석: {collection_name}\n")
    
    # Collection 정보 가져오기
    collection_info = client.get_collection(collection_name)
    total_points = collection_info.points_count
    
    print(f"전체 문서 수: {total_points:,}개\n")
    
    # 노동법 목록 정의
    labor_laws = {
        "근로기준법", "근로자퇴직급여보장법", "최저임금법", "산업안전보건법",
        "남녀고용평등법", "고용보험법", "산재보상보험법", "노동조합법",
        "파견근로자보호법", "기간제법", "직업안정법", "노동위원회법",
        "근로자직업능력개발법", "고용정책기본법", "외국인근로자법",
        "보험료징수", "산업재해보상보험"  # 보험료 관련 법률 추가
    }
    
    print("전체 문서 분석 중... (시간이 다소 걸릴 수 있습니다)\n")
    
    # Scroll API로 전체 문서 가져오기
    law_names = []
    offset = None
    batch_count = 0
    
    while True:
        result = client.scroll(
            collection_name=collection_name,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )
        
        points, offset = result
        
        if not points:
            break
        
        batch_count += 1
        if batch_count % 10 == 0:
            print(f"  진행 중... {len(law_names)}개 문서 처리됨")
        
        for point in points:
            payload = point.payload
            law_name = payload.get("law_name", "")
            if law_name:
                law_names.append(law_name)
        
        if offset is None:
            break
    
    print(f"✅ 전체 {len(law_names)}개 문서 분석 완료\n")
    
    # 법령명 통계
    law_counter = Counter(law_names)
    
    print("=" * 60)
    print("📋 법령 분포 (상위 20개)")
    print("=" * 60)
    
    labor_count = 0
    non_labor_count = 0
    
    for law_name, count in law_counter.most_common(20):
        is_labor = any(labor_law in law_name for labor_law in labor_laws)
        category = "✅ 노동법" if is_labor else "❌ 노동법 외"
        
        if is_labor:
            labor_count += count
        else:
            non_labor_count += count
        
        print(f"{category:15} | {law_name:40} | {count:4}개")
    
    print("=" * 60)
    
    # 전체 통계
    total_analyzed = labor_count + non_labor_count
    labor_ratio = (labor_count / total_analyzed * 100) if total_analyzed > 0 else 0
    non_labor_ratio = (non_labor_count / total_analyzed * 100) if total_analyzed > 0 else 0
    
    print(f"\n📊 전체 통계 (총 {total_analyzed:,}개)")
    print(f"  ✅ 노동법:     {labor_count:,}개 ({labor_ratio:.1f}%)")
    print(f"  ❌ 노동법 외:  {non_labor_count:,}개 ({non_labor_ratio:.1f}%)")
    
    # 노동법 외 법령 상세 목록
    print("\n" + "=" * 60)
    print("❌ 노동법 외 법령 상세 목록")
    print("=" * 60)
    
    non_labor_laws = []
    for law_name, count in law_counter.items():
        is_labor = any(labor_law in law_name for labor_law in labor_laws)
        if not is_labor:
            non_labor_laws.append((law_name, count))
    
    non_labor_laws.sort(key=lambda x: x[1], reverse=True)
    
    for law_name, count in non_labor_laws:
        print(f"  - {law_name:50} ({count}개)")
    
    print("\n" + "=" * 60)
    print("💡 권장 사항")
    print("=" * 60)
    
    if non_labor_count > 0:
        print("⚠️  노동법 외 법령이 발견되었습니다.")
        print("   다음 중 하나를 선택하세요:")
        print("   1. Qdrant collection에서 노동법 외 문서 삭제")
        print("   2. Generate 노드에서 category='기타'일 때 답변 거부 로직 추가")
    else:
        print("✅ 모든 문서가 노동법 관련입니다.")

if __name__ == "__main__":
    analyze_qdrant_laws()
