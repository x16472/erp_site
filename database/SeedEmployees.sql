-- 由既有員工清單轉換的新結構初始資料；僅執行一次，不覆寫後台維護結果。
SET XACT_ABORT ON;
IF NOT EXISTS (SELECT 1 FROM dbo.ImportStates WITH (UPDLOCK,HOLDLOCK) WHERE ImportSourceNo=N'EmployeeSeed.v1')
BEGIN
INSERT dbo.Departments(DepartmentNo,IsActive,UpdatedBy)
SELECT source.DepartmentNo,1,N'initialization' FROM (VALUES
(N'資訊部'),
(N'營運部'),
(N'管理部'),
(N'製造部'),
(N'財務部'),
(N'人事部')
) source(DepartmentNo) WHERE NOT EXISTS (SELECT 1 FROM dbo.Departments existing WHERE existing.DepartmentNo=source.DepartmentNo);
INSERT dbo.Employees(EmployeeNo,EmployeeName,Gender,Age,DepartmentNo,PositionName,Traits,Biography,PhotoFile,IsActive,UpdatedBy)
SELECT source.*,1,N'initialization' FROM (VALUES
(N'K001',N'王俊凱',N'男',31,N'資訊部',N'MIS資訊管理師',N'沉穩理性、邏輯清晰、重視穩定',N'具資訊工程與企業系統維運經驗，負責網路、門禁、資訊安全及營運設備整合。',N'K001.png'),
(N'K002',N'凝玥',N'女',26,N'資訊部',N'MIS資訊工程師',N'思路敏捷、跨域整合',N'具數理、生物資訊、電通科學與 IoT 能力，負責系統整合、自動化設備與資料服務維運。',N'K002.png'),
(N'K003',N'吳佳蓉',N'女',30,N'營運部',N'專案經理',N'成熟穩重、善於傾聽、組織力強',N'具多年專案管理與團隊帶領經驗，負責客戶溝通、進度控管、資源協調與成果驗收。',N'K003.png'),
(N'K004',N'林詩涵',N'女',28,N'營運部',N'業務專員',N'細心敏銳、有藝術氣質、擅長提案',N'具跨文化交流與視覺企劃經驗，負責商務提案、合作夥伴需求盤點及品牌專案協調。',N'K004.png'),
(N'K005',N'蔡明宏',N'男',44,N'管理部',N'管理經理',N'穩重可靠、熱心協作、具領導力',N'具採購與場域管理經驗，負責莊園、工匠街及各營業據點的設施維護與供應商管理。',N'K005.png'),
(N'K006',N'許淑芬',N'女',49,N'管理部',N'餐飲營運組長',N'親切沉著、注重品質、耐心細緻',N'具餐飲證照與現場管理經驗，負責可可藝術沙龍餐飲製作、食材驗收及衛生管理。',N'K006.png'),
(N'K007',N'李志偉',N'男',28,N'營運部',N'國際業務專員',N'外向幽默、創意豐富、溝通靈活',N'具應用外語與商務簡報能力，負責海外合作、雙語提案與跨文化客戶關係。',N'K007.png'),
(N'K008',N'陳美玲',N'女',41,N'管理部',N'環境管理專員',N'勤奮踏實、低調務實、責任感強',N'具場域清潔與環境維護經驗，負責公共區域品質、物資管理與據點環境改善。',N'K008.jpg'),
(N'K009',N'林俊宏',N'男',38,N'製造部',N'生產管理主管',N'嚴謹負責、條理分明、重視標準',N'具流程管理與團隊領導經驗，負責工匠街排程、製程標準、品質稽核與產能規劃。',N'K009.png'),
(N'K010',N'黃建志',N'男',27,N'製造部',N'客製設計顧問',N'富有創意、審美細膩',N'具視覺藝術與手工製作背景，負責客製設計、材質搭配、樣品開發與品牌影像協作。',N'K010.png'),
(N'K011',N'黃雅婷',N'女',27,N'製造部',N'工程顧問',N'親切穩定、審美敏銳、注重細節',N'具藝術與聲音設計專業，負責客製產品提案、工藝品質溝通與沙龍展演專案。',N'K011.png'),
(N'K012',N'張麗華',N'女',46,N'管理部',N'營養管理師',N'溫和親切、重視健康、耐心細緻',N'具營養專業與餐飲規劃經驗，負責餐飲配方、過敏原管理、品質標示及健康方案。',N'K012.png'),
(N'K013',N'劉思妍',N'女',25,N'管理部',N'倉管專員',N'行動力強、協調敏捷、重視安全',N'具現場管理背景，負責倉儲盤點、物料調度、裝卸安全與跨據點配送協調。',N'K013.png'),
(N'K014',N'陳怡君',N'女',26,N'管理部',N'行政專員',N'活潑開朗、善於溝通、反應靈活',N'具企管與內容企劃背景，負責共同體活動、行政流程、對外窗口與跨部門協調。',N'K014.jpg'),
(N'K015',N'鄭雅文',N'女',36,N'財務部',N'會計專員',N'細心謹慎、條理清楚、重視稽核',N'具會計師專業與事務所經驗，負責帳務、成本歸集、憑證覆核及管理報表。',N'K015.jpg'),
(N'K016',N'林佑君',N'女',32,N'財務部',N'出納專員',N'可靠細心、反應穩定、責任感強',N'具企業管理與出納經驗，負責款項確認、銀行往來、零用金、供應商付款與每日資金核對。',N'K016.jpg'),
(N'K017',N'劉雅茹',N'女',30,N'財務部',N'薪資及稅務專員',N'理性務實、擅長分析、規劃周全',N'具會計資訊及企業共享中心經驗，負責薪資、獎金、保險、退休金、所得扣繳與人事成本統計。',N'K017.png'),
(N'K018',N'陳婉婷',N'女',42,N'財務部',N'會計經理',N'理性沉穩、邏輯清晰、洞察數據',N'具財務金融與商業分析經驗，負責年度預算、事業成本、營收預估、資金配置及經營分析報表。',N'K018.png'),
(N'K019',N'王雅芳',N'女',32,N'人事部',N'人事經理',N'細心周到、善於協調、重視穩定',N'具人力資源實務經驗，負責招募、考勤、人才發展、制度維護與員工福利。',N'K019.jpg'),
(N'K020',N'周佩君',N'女',33,N'人事部',N'管理組長',N'敏銳同理、善於傾聽、情緒穩定',N'具心理諮商與組織溝通背景，負責員工關係、福利諮詢、職場支持與爭議協調。',N'K020.jpg'),
(N'K021',N'張欣怡',N'女',29,N'人事部',N'管理專員',N'溫暖可靠、反應迅速、細心負責',N'具臨床照護經驗，負責職場健康、緊急應變、福利資源與作業環境風險追蹤。',N'K021.png'),
(N'K022',N'陳佑淇',N'女',18,N'人事部',N'管理專員',N'率直真誠、觀察敏銳',N'具豐富的社群互動經驗，負責成員福利活動、內部關懷、需求彙整與行政支援。',N'K022.png')
) source(EmployeeNo,EmployeeName,Gender,Age,DepartmentNo,PositionName,Traits,Biography,PhotoFile)
WHERE NOT EXISTS (SELECT 1 FROM dbo.Employees existing WHERE existing.EmployeeNo=source.EmployeeNo);
INSERT dbo.ImportStates(ImportSourceNo,ImportedRows,ImportedAt) VALUES(N'EmployeeSeed.v1',22,SYSDATETIME());
END;
