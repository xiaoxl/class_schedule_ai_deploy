from dataclasses import replace
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd
from fastapi.testclient import TestClient
from class_schedule import Section, NormalClass, FourCreditClass, HybridClass, CoreqClass, CrossListingClass, LabClass, LectureLabClass, Schedule
from class_schedule import webapp
from class_schedule.config_schema import CourseRelationshipSchema
from class_schedule.config_inference import _courses_toml
from class_schedule.schedule_io import read_schedule


def row(number='1013', section='001', **changes):
    values=dict(subject='MATH',number=number,section=section,instructor='Alice',building='Science',room='10',time_slot='MWF 9:00am',duration=50,type='CLAS')
    values.update(changes)
    return Section(**values)


def paired_classes():
    lab=(row('3260',subject='CHEM',type='LAB',duration=50),row('3260',subject='CHEM',type='LAB',duration=170,room='20'))
    return [
        FourCreditClass((row('1014'),row('1014',time_slot='T 9:00am',duration=80))),
        HybridClass((row(section='F01'),)),
        CoreqClass((row('1113'),row('0903',time_slot='MWF 10:00am'))),
        CrossListingClass((row('5173'),row('4173',subject='STAT'))),
        LabClass(lab),
        LectureLabClass((row('3264',subject='CHEM'),*lab)),
    ]


class SectionEditTests(unittest.TestCase):
    def test_strings_and_invalid_input(self):
        original=NormalClass((row(section='1'),))
        changed=original.change_section('001')
        self.assertEqual(changed.sections[0].section,'001')
        self.assertEqual(original.sections[0].section,'1')
        self.assertIsInstance(row(section=1).section,str)
        for value in [1,None,'','   ','00 1']:
            with self.subTest(value=value),self.assertRaises(ValueError):original.change_section(value)
        with self.assertRaises(IndexError):original.change_section('002',record=3)

    def test_every_required_pair_links_from_every_row(self):
        for item in paired_classes():
            for index in range(len(item.sections)):
                with self.subTest(kind=type(item).__name__,index=index):
                    updated=item.change_section('002',record=index)
                    self.assertEqual({r.section for r in updated.sections},{'002'})
                    self.assertEqual(item.edit_targets('section',index),tuple(range(len(item.sections))))
                    self.assertIn('section',item.editable_fields(index))
                    self.assertEqual({r.section for r in item.apply_edit('section',index,section='003').sections},{'003'})

    def test_cross_listing_without_same_section_rule_is_independent(self):
        item=CrossListingClass.from_configured_sections((row(section='001'),row(section='H01')),synced_fields=frozenset({'instructor'}))
        updated=item.change_section('002',record=0)
        self.assertEqual([r.section for r in updated.sections],['002','H01'])
        self.assertEqual(updated.synced_fields,item.synced_fields)
        schedule=Schedule([item])
        with self.assertRaises(ValueError):schedule.change_section(item.sections[0].course_id,'H01')
        self.assertIs(schedule.classes[0],item)

    def test_schedule_collision_checks_all_linked_members_without_mutation(self):
        item=paired_classes()[2]
        other=NormalClass((row('0903',section='002'),))
        schedule=Schedule([item,other])
        with self.assertRaisesRegex(ValueError,'Section already exists'):schedule.change_section(item.sections[0].course_id,'002')
        self.assertIs(schedule.classes[0],item)
        schedule.change_section(item.sections[0].course_id,'003')
        self.assertEqual({r.section for r in schedule.classes[0].sections},{'003'})
        distinct=Schedule([NormalClass((row(section='1'),)),NormalClass((row(section='002'),))])
        distinct.change_section('MATH 1013-002','001')
        self.assertEqual(distinct.classes[1].sections[0].section,'001')

    def test_csv_and_excel_roundtrip_preserve_zeros_and_relationship(self):
        item=CoreqClass((row('1113'),row('0903',time_slot='MWF 10:00am')))
        relationship=CourseRelationshipSchema(kind='coreq',members=['MATH 1113 001','MATH 0903 001'])
        changed=Schedule([item]);changed.change_section('MATH 1113-001','007')
        with tempfile.TemporaryDirectory() as folder:
            for suffix in ['csv','xlsx']:
                path=Path(folder)/f'schedule.{suffix}'
                if suffix=='csv':changed.to_dataframe().to_csv(path,index=False)
                else:changed.to_raw_excel(path)
                rebuilt=read_schedule(path,relationships=[relationship])
                self.assertEqual(len(rebuilt),1)
                self.assertIsInstance(rebuilt.classes[0],CoreqClass)
                self.assertEqual({r.section for r in rebuilt.classes[0].sections},{'007'})
                self.assertEqual({r.source_section for r in rebuilt.classes[0].sections},{'001'})


class SectionEditApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        for name in ['CONFIG_DIR','WORK_ROOT','OUTPUT_ROOT']:
            patcher=patch.object(webapp,name,self.root/name);patcher.start();self.addCleanup(patcher.stop)
        self.client=TestClient(webapp.create_app());self.addCleanup(self.client.close)
        source=Schedule([paired_classes()[2],NormalClass((row('0903',section='002'),))]).to_dataframe().to_csv(index=False).encode()
        response=self.client.post('/api/configuration-packages',data={'upload_mode':'create'},files={'config_files':('test.csv',source)})
        self.assertEqual(response.status_code,200,response.text)
        self.package=response.json()['package_id']
        response=self.client.get('/api/schedule',params={'package':self.package})
        self.assertEqual(response.status_code,200,response.text)
        self.body=response.json();self.baseline=self.records()

    def records(self):return [row for item in self.body['classes'] for row in item['sections']]

    def edit(self,field,value):
        index=next(i for i,item in enumerate(self.body['classes']) if item['kind']=='CoreqClass')
        item=self.body['classes'][index];target=item['sections'][0]
        response=self.client.post('/api/edit',json={'package':self.package,'records':self.records(),'class_index':index,'record_index':0,'expected_course_ids':item['course_ids'],'expected_record':{'subject':target['Subject'],'number':target['Number'],'section':target['Section'],'expected_time_slot':target['Time Slot']},'field':field,'value':value})
        if response.status_code==200:self.body=response.json()
        return response

    def test_collision_then_repeat_edit_export_and_save(self):
        self.assertEqual(self.edit('section','002').status_code,400)
        self.assertEqual(self.edit('section',7).status_code,400)
        response=self.edit('section','007');self.assertEqual(response.status_code,200,response.text)
        response=self.edit('instructor','Alice');self.assertEqual(response.status_code,200,response.text)
        response=self.edit('section','008');self.assertEqual(response.status_code,200,response.text)
        response=self.client.post('/api/export/schedule',json={'package':self.package,'records':self.records()})
        self.assertEqual(response.status_code,200,response.text if response.status_code!=200 else '')
        self.assertIn('008',pd.read_excel(io.BytesIO(response.content),dtype=str)['Section'].tolist())
        response=self.client.post('/api/save',json={'package':self.package,'term':self.package,'records':self.records(),'baseline_records':self.baseline})
        self.assertEqual(response.status_code,200,response.text)
        self.assertFalse(response.json().get('fork_error'),response.text)
        fork=response.json()['forked_package']
        loaded=self.client.get('/api/schedule',params={'package':fork})
        self.assertEqual(loaded.status_code,200,loaded.text)
        item=next(item for item in loaded.json()['classes'] if item['kind']=='CoreqClass')
        self.assertEqual({r['Section'] for r in item['sections']},{'008'})
        self.assertEqual({r['Instructor'] for r in item['sections']},{'Alice'})

if __name__=='__main__':unittest.main()
