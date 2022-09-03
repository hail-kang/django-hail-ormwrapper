import re
from copy import deepcopy
from collections import defaultdict

class HQ:
    '''
    HailORMWrapper의 where에서 사용하기 위한 클래스
    Django의 Q클래스를 본따 HailQ이름을 줄인 HQ로 명명함
    '''
    
    AND = 0
    OR = 1

    def __init__(self, **kwargs):
        '''
        kwargs를 pack하며 받아 conditions 멤버변수를 구성함
        kwargs는 { field: condition, } 형태의 dict구조임
        field는 문자열이며, 필터링할 필드명을 나타냄.
        condition은 단순 값, 함수, HQ인스턴스를 가질 수 있음
        condition이 단순 값일 경우엔 field가 field__operator 형태인지 확인하고
        파싱하여 conditions를 재구성함.
        '''
        self.conditions = {}
        for field, condition in kwargs.items():
            if not callable(condition) and not isinstance(condition, HQ):
                if re.search('\w*(?=__contains)$', field):
                    parsed_field = re.search('\w*(?=__contains)', field).group(0)
                    def closure(condition):
                        return lambda x: bool(re.search(condition, x))
                    self.conditions[parsed_field] = closure(condition)
                elif re.search('\w*(?=__icontains)$', field):
                    parsed_field = re.search('\w*(?=__icontains)', field).group(0)
                    def closure(condition):
                        return lambda x: bool(re.search(condition, x, re.I))
                    self.conditions[parsed_field] = closure(condition)
                elif re.search('\w*(?=__lt)$', field):
                    parsed_field = re.search('\w*(?=__lt)', field).group(0)
                    def closure(condition):
                        return lambda x: x < condition
                    self.conditions[parsed_field] = closure(condition)
                elif re.search('\w*(?=__lte)$', field):
                    parsed_field = re.search('\w*(?=__lt)', field).group(0)
                    def closure(condition):
                        return lambda x: x <= condition
                    self.conditions[parsed_field] = closure(condition)
                elif re.search('\w*(?=__gt)$', field):
                    parsed_field = re.search('\w*(?=__gt)', field).group(0)
                    def closure(condition):
                        return lambda x: x > condition
                    self.conditions[parsed_field] = closure(condition)
                elif re.search('\w*(?=__gte)$', field):
                    parsed_field = re.search('\w*(?=__gte)', field).group(0)
                    def closure(condition):
                        return lambda x: x >= condition
                    self.conditions[parsed_field] = closure(condition)
                elif re.search('\w*(?=__neq)$', field):
                    parsed_field = re.search('\w*(?=__neq)', field).group(0)
                    def closure(condition):
                        return lambda x: x != condition
                    self.conditions[parsed_field] = closure(condition)
                elif re.search('\w*(?=__in)$', field):
                    parsed_field = re.search('\w*(?=__in)', field).group(0)
                    def closure(condition):
                        return lambda x: x in condition
                    self.conditions[parsed_field] = closure(condition)
                elif re.findall('(\w*)__includes__(\w*)', field):
                    parsed_field, condition_field = re.findall('(\w*)__includes__(\w*)', field)[0]
                    def closure(condition):
                        def test(items):
                            if not items:
                                return False
                            return condition in map(lambda item: item[condition_field], items)
                        return test
                    self.conditions[parsed_field] = closure(condition)
                else:
                    def closure(condition):
                        return lambda x: x == condition
                    self.conditions[field] = closure(condition)
            else:
                self.conditions[field] = condition


    def __and__(self, other):
        if not isinstance(other, HQ):
            raise Exception('Only HQ instances')
        
        tq = HQ()
        tq.conditions = (self.conditions, other.conditions, HQ.AND)

        return tq

    def __or__(self, other):
        if not isinstance(other, HQ):
            raise Exception('Only HQ instances')
        
        tq = HQ()
        tq.conditions = (self.conditions, other.conditions, HQ.OR)

        return tq

    def __check(self, item, conditions):
        '''
        예를들어 HQ = (HQ1 & HQ2) | HQ3 이라하자.
        각각의 멤버변수 conditions를 con로 표현하면
        con = ((con1, con2, AND), con3, OR)으로 저장되어 있다.
        재귀적으로 계산하는 과정을 따라가면 아래와 같다.
        __check(con)    = __check(((con1, con2, AND), con3, OR))
                        = __check((con1, con2, AND)) | __check(con3)
                        = (__check(con1) & __check(con2)) | __check(con3)
        '''
        if isinstance(conditions, tuple):
            if conditions[2] == HQ.AND:
                return self.__check(item, conditions[0]) & self.__check(item, conditions[1])
            elif conditions[2] == HQ.OR:
                return self.__check(item, conditions[0]) | self.__check(item, conditions[1])
            else:
                raise Exception('Unexpected operator')
        
        if item is None:
            return False

        return all([
            condition.check(item.get(field)) 
            if isinstance(condition, HQ) 
            else condition(item.get(field)) 
            for field, condition in conditions.items()])
        
    def check(self, item):
        '''
        item은 dict구조를 갖는 값. 외부에서는 item만 전달받는 check메소드를 호출함.
        멤버변수 conditions에는 AND또는 OR연산으로 인한 과정이 기록되어 있고,
        해당 기록을 효과적으로 검사하기위해 재귀적인 논리를 채택함.
        따라서 내부적으로는 __check메소드를 호출하여 재귀적으로 검사함.
        '''
        return self.__check(item, self.conditions)


class HailORMWrapper:
    '''
    Django ORM을 wrapping하기 위한 클래스
        - ORM을 사용함에도 코드 작성자간의 형식 통일이 잘 이루어지지 않음
        - 특히 join이 포함된 연산은 db에서 실행시키키보다 인스턴스로 가져와 연산하기를 권장
        - 그러다보니 join 연산이 포함될 경우, 코드스타일마다 각기 다른 코드가 생성됨
        - 일반적인 결과 포맷을 몇가지 정해둔 뒤, 그에 맞춰 해당 클래스를 설계함
        - 해당 클래스를 사용하면 동일한 결과 포맷에 대해, 동일한 코드 스타일로 작성할수 있도록 도움을 줄 수 있음
    '''

    def __init__(self, model, **kwargs):
        '''
        parameter
            - model: db에 쿼리요청을 보낼 model
            - name: 자신이 child 요소일 때, parent에서 어떤 key값으로 불릴 지 지정함
            - reverse: 만약 parant:child = 1:N 관계라면 reverse를 True로 설정할 수 있음
                (추가 설명을 하자면, 쿼리를 하는 기준 테이블이 parent가 되며, join하는 테이블이 child이다.
                예를 들어 order와 order_group은 N:1 관계이고 order에 대해 쿼리를 하면 
                {idx:1, order_group:{idx:1}}과 같은 결과를 얻을 수 있고 reverse=False이다
                반면에 order_group과 order는 1:N 이므로 order_group에 대해 쿼리를 하면
                {idx:1, order:[{idx:1}, {idx:2}]}와 같은 결과를 얻을 수 있고 reverse=True이다)
            - fk: reverse가 False일 때는 parent의 foreign_key, reverse가 True일 때는 child의 foreign_key
            - pk: reverse가 False일 때는 child의 primary_key, reverse가 True일 때는 parent의 primary_key
            - fields: 결과에서 보여줄 필드명 목록. 기본값은 필드 전체. 아직 별칭 기능은 구현하지 않음
            - joins: join연산을 수행할 목록, List[HailORMWrapper]
        '''
        self.model = model
        self.name = kwargs.get('name', self.model._meta.db_table)
        self.reverse = kwargs.get('reverse', False)
        self.fk = kwargs.get('fk')
        self.pk = kwargs.get('pk')
        self.fields = kwargs.get('fields', [field.name for field in self.model._meta.fields])
        self.joins = kwargs.get('joins', [])
        '''
        생성자에서 저장되지 않지만 모든 멤버변수를 보여주기 위해 None으로 초기화 하는 멤버변수
            - conditions: where 메소드에서 전달받을 값을 전달받아 저장될 변수
            - indexing: list 메소드에서 계산되어 저장될 변수
            - caching: list 메소드의 결과값을 저장할 변수
        '''
        self.conditions = None
        self.indexing = None
        self.caching = None

    def where(self, tq=None, **kwargs):
        '''
        HQ 인스턴스를 전달받아 conditions 멤버변수에 저장하거나,
        kwargs를 직접 입력받아 HQ 인스턴스를 생성하여 conditions 멤버변수에 저장함
        '''
        if tq:
            self.conditions = tq
        else:
            self.conditions = HQ(**kwargs)
        return self

    def one(self):
        '''
        list 메소드를 실행시킨 결과값의 첫 번째 요소를 반환함
        ---------------------------------------------------
        만약 리스트 길이가 0이라면 IndexError을 발생시킬 것인데,
        길이를 검사해서 None을 반한하도록 할 것인지, 커스텀 Exception을 반환할 것인지,
        그냥 이대로 내비둬도 문제되는 사항이 없을지 고민.
        '''
        return self.list()[0]

    def list(self):
        '''
        모든 연산이 수행하고, dict 자료형으로 결과를 반환하는 메소드
        어떤 필드를 보여줄 것인지, 어떤 조건으로 필터링 할 건지, 어떤 테이블과 join할 것인지
        모두 해당 메소드에서 연산을 수행함
        '''

        if self.caching is not None:
            return self.caching

        # 반환할 결과값 변수 results 초기화,
        results = []

        # 정해둔 fields에 대해 기준 테이블의 모든 row 쿼리하여 parents변수에 저장
        parents = self.model.objects.all().values(*self.fields)

        # join을 빠르게 수행하기 위해 indexing 저장
        for join in self.joins:
            if join.reverse:
                many_child = defaultdict(list)
                for child in join.list():
                    many_child[child[join.fk]].append(child)
                join.indexing = many_child
            else:
                join.indexing = { e[join.pk]: e for e in join.list() }

        # join을 수행하는 부분
        for parent in parents:
            results.append({
                **parent,
                **{
                    join.name: join.indexing.get(parent.get(join.pk if join.reverse else join.fk))
                    for join in self.joins
                }
            })

        # filter를 수행하는 부분
        if self.conditions:
            results = filter(self.conditions.check, results)
            results = list(results)

        self.caching = results

        return results

    def paginated(self, size, page):
        limit = int(size * page)
        offset = int(limit - size)
        return {
            'page_info': {
                'total_count': len(self.list()),
                'limit': limit,
                'offset': offset,
            },
            'data': self.list()[offset:limit]
        }

    def join(self, other):
        results = []
        parents = self.list()

        if other.reverse:
            many_child = defaultdict(list)
            for child in other.list():
                many_child[child[other.fk]].append(child)
            other.indexing = many_child
        else:
            other.indexing = { e[other.pk]: e for e in other.list() }

        for parent in parents:
            results.append({
                **parent,
                **{
                    join.name: join.indexing.get(parent.get(join.pk if join.reverse else join.fk))
                    for join in self.joins
                }
            })

        kwargs = {
            'model': self.model,
            'name': self.name,
            'reverse': self.reverse,
            'fk': self.fk,
            'pk': self.pk,
            'fields': self.fields,
            'joins': deepcopy(self.joins)
        }
        kwargs['joins'].append(other)
        instance = HailORMWrapper(**kwargs)
        instance.caching = results

        return instance
        


'''
CamelCase를 따르는 클래스 명명 규칙과, 클래스 목적에 맞는 이름을 붙이기 위해
HailORMWrapper라 명명했지만, 실제 사용은 인스턴스를 잘 사용하지 않고,
결과값만 얻기 위해 거의 함수처첨 사용하게 되므로 함수 형태의 재명명을 함.
특히 기능의 직관성을 높이기 위해 where와 같은 메소드와 어울리는 이름인 select_from으로 지음
'''
select_from = HailORMWrapper