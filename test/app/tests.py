from test_plus import TestCase
from .models import FirstModel, SecondModel, ThirdModel

import sys
from os import path
sys.path.append(path.dirname( path.dirname( path.abspath(__file__) ) ))
sys.path.append(path.dirname(path.abspath(path.dirname(path.abspath(path.dirname(__file__))))))
from ormwrapper import select_from

class MyTestCase(TestCase):
    def make_key_value(self):
        import uuid
        import random
        return {
            'key': str(uuid.uuid4()),
            'value': random.randint(1, 10000),
        }

    def do_First_생성(self):
        test = FirstModel(**self.make_key_value())
        test.save()
        return test

    def do_Second_생성(self, first_id):
        test = SecondModel(**self.make_key_value(), first_id=first_id)
        test.save()
        return test

    def do_First_조회(self, first_id):
        test = \
            select_from(
                model=FirstModel,
                fields=['id', 'key', 'value'],
            ).where(
                id=first_id
            ).one()
        return test

    def do_First_조회_nesting_Second(self, first_id):
        test = \
            select_from(
                model=FirstModel,
                fields=['id', 'key', 'value'],
                joins=[
                    select_from(
                        name='second',
                        model=SecondModel,
                        fields=['id', 'key', 'value', 'first_id'],
                        fk='id',
                        pk='first_id',
                    )
                ]
            ).where(
                id=first_id
            ).one()
        return test

    def do_First_조회_many_nesting_Second(self, first_id):
        test = \
            select_from(
                model=FirstModel,
                fields=['id', 'key', 'value'],
                joins=[
                    select_from(
                        name='seconds',
                        model=SecondModel,
                        fields=['id', 'key', 'value', 'first_id'],
                        fk='id',
                        pk='first_id',
                        many=True,
                    )
                ]
            ).where(
                id=first_id
            ).one()
        return test

    def do_First_목록_조회(self):
        tests = FirstModel.objects.all()
        return tests

    def do_First_Second_목록_조회(self):
        tests = \
            select_from(
                model=FirstModel,
                fields=['id', 'key', 'value'],
                joins=[
                    select_from(
                        name='second',
                        model=SecondModel,
                        fields=['id', 'key', 'value', 'first_id'],
                        fk='id',
                        pk='first_id',
                    )
                ]
            ).list()
        return tests

    def test_First_생성_및_조회(self):
        first_obj = self.do_First_생성()
        first_dict = self.do_First_조회(first_obj.id)
        self.assertTrue(first_obj.id == first_dict['id'])
        self.assertTrue(first_obj.key == first_dict['key'])
        self.assertTrue(first_obj.value == first_dict['value'])

    def test_First_생성_및_조회_nesting_Second(self):
        first_obj = self.do_First_생성()
        second_obj = self.do_Second_생성(first_obj.id)
        first_dict = self.do_First_조회_nesting_Second(first_obj.id)
        second_dict = first_dict['second']
        self.assertTrue(first_obj.id == first_dict['id'])
        self.assertTrue(first_obj.key == first_dict['key'])
        self.assertTrue(first_obj.value == first_dict['value'])
        self.assertTrue(second_obj.id == second_dict['id'])
        self.assertTrue(second_obj.key == second_dict['key'])
        self.assertTrue(second_obj.value == second_dict['value'])

    def test_First_조회_many_nesting_Second(self):
        first_obj = self.do_First_생성()
        second_obj_1 = self.do_Second_생성(first_obj.id)
        second_obj_2 = self.do_Second_생성(first_obj.id)
        first_dict = self.do_First_조회_many_nesting_Second(first_obj.id)
        print(first_dict)
        seconds = first_dict['seconds']
        self.assertTrue(first_obj.id == first_dict['id'])
        self.assertTrue(first_obj.key == first_dict['key'])
        self.assertTrue(first_obj.value == first_dict['value'])
        self.assertTrue(len(seconds) == 2)
        

    def test_First_목록_조회(self):
        for _ in range(10):
            self.do_First_생성()
        
        test_list = self.do_First_목록_조회()
        self.assertEqual(len(test_list), 10)

    def test_Second_목록_조회(self):
        for _ in range(10):
            first = self.do_First_생성()
            self.do_Second_생성(first.id)
        
        test_list = self.do_First_Second_목록_조회()
        print(test_list)
        self.assertEqual(len(test_list), 10)