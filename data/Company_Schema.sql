USE [Company_New]
GO
/****** 物件:  Table [dbo].[Company_Attendance]    指令碼日期: 2026/8/5 下午 01:59:40 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Company_Attendance](
	[attendance_id] [bigint] IDENTITY(1,1) NOT NULL,
	[employee_id] [nvarchar](20) NOT NULL,
	[action] [nvarchar](20) NOT NULL,
	[clocked_at] [datetime2](7) NOT NULL,
	[source_ip] [nvarchar](45) NULL,
	[clocked_at_utc] [datetime2](7) NULL,
	[work_date] [date] NULL,
PRIMARY KEY CLUSTERED 
(
	[attendance_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** 物件:  Table [dbo].[Company_Department]    指令碼日期: 2026/8/5 下午 01:59:40 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Company_Department](
	[department_id] [int] IDENTITY(1,1) NOT NULL,
	[department_name] [nvarchar](50) NOT NULL,
	[is_active] [bit] NOT NULL,
	[updated_by] [nvarchar](80) NOT NULL,
	[updated_at] [datetime2](7) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[department_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
UNIQUE NONCLUSTERED 
(
	[department_name] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** 物件:  Table [dbo].[Company_ImportState]    指令碼日期: 2026/8/5 下午 01:59:40 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Company_ImportState](
	[source_key] [nvarchar](100) NOT NULL,
	[source_modified] [bigint] NOT NULL,
	[source_size] [bigint] NOT NULL,
	[imported_rows] [int] NOT NULL,
	[imported_at] [datetime2](7) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[source_key] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** 物件:  Table [dbo].[Company_OperationCategory]    指令碼日期: 2026/8/5 下午 01:59:40 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Company_OperationCategory](
	[category_code] [nvarchar](10) NOT NULL,
	[display_order] [tinyint] NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[category_code] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
UNIQUE NONCLUSTERED 
(
	[display_order] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** 物件:  Table [dbo].[Company_OperationSubmission]    指令碼日期: 2026/8/5 下午 01:59:40 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Company_OperationSubmission](
	[submission_id] [nvarchar](40) NOT NULL,
	[operation_date] [date] NOT NULL,
	[campus_code] [nvarchar](12) NOT NULL,
	[category_code] [nvarchar](10) NOT NULL,
	[quantity] [int] NOT NULL,
	[note] [nvarchar](200) NULL,
	[status] [nvarchar](20) NOT NULL,
	[submitted_at] [datetime2](7) NOT NULL,
	[submitted_by] [nvarchar](20) NULL,
PRIMARY KEY CLUSTERED 
(
	[submission_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** 物件:  Table [dbo].[Company_Staff]    指令碼日期: 2026/8/5 下午 01:59:40 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Company_Staff](
	[employee_id] [nvarchar](20) NOT NULL,
	[display_name] [nvarchar](50) NOT NULL,
	[gender] [nvarchar](10) NULL,
	[age] [smallint] NULL,
	[department] [nvarchar](50) NOT NULL,
	[position] [nvarchar](50) NOT NULL,
	[traits] [nvarchar](200) NULL,
	[biography] [nvarchar](1000) NULL,
	[photo_file] [nvarchar](100) NULL,
	[is_active] [bit] NOT NULL,
	[updated_by] [nvarchar](80) NOT NULL,
	[updated_at] [datetime2](7) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[employee_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** 物件:  Table [dbo].[Company_TrainingDocument]    指令碼日期: 2026/8/5 下午 01:59:40 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Company_TrainingDocument](
	[document_id] [int] IDENTITY(1,1) NOT NULL,
	[file_name] [nvarchar](260) NOT NULL,
	[title] [nvarchar](200) NOT NULL,
	[role_category] [nvarchar](80) NOT NULL,
	[source_size] [bigint] NOT NULL,
	[source_modified] [nvarchar](40) NOT NULL,
	[is_active] [bit] NOT NULL,
	[imported_at] [datetime2](7) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[document_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
UNIQUE NONCLUSTERED 
(
	[file_name] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** 物件:  Table [dbo].[Company_TrainingQuestion]    指令碼日期: 2026/8/5 下午 01:59:40 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Company_TrainingQuestion](
	[question_id] [int] IDENTITY(1,1) NOT NULL,
	[document_id] [int] NULL,
	[category] [nvarchar](50) NOT NULL,
	[question] [nvarchar](500) NOT NULL,
	[options_json] [nvarchar](max) NOT NULL,
	[correct_index] [tinyint] NOT NULL,
	[explanation] [nvarchar](1000) NOT NULL,
	[is_active] [bit] NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[question_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** 物件:  Table [dbo].[Company_TrainingSection]    指令碼日期: 2026/8/5 下午 01:59:40 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Company_TrainingSection](
	[section_id] [bigint] IDENTITY(1,1) NOT NULL,
	[document_id] [int] NOT NULL,
	[section_order] [int] NOT NULL,
	[heading] [nvarchar](300) NOT NULL,
	[content] [nvarchar](max) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[section_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
 CONSTRAINT [UQ_Company_TrainingSection_Order] UNIQUE NONCLUSTERED 
(
	[document_id] ASC,
	[section_order] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** 物件:  Table [dbo].[Company_WebSettings]    指令碼日期: 2026/8/5 下午 01:59:40 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Company_WebSettings](
	[id] [int] NOT NULL,
	[theme] [nvarchar](20) NOT NULL,
	[hero_title] [nvarchar](60) NOT NULL,
	[hero_subtitle] [nvarchar](180) NOT NULL,
	[announcement] [nvarchar](160) NULL,
	[updated_by] [nvarchar](80) NOT NULL,
	[updated_at] [datetime2](7) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
ALTER TABLE [dbo].[Company_Attendance] ADD  DEFAULT (sysdatetime()) FOR [clocked_at]
GO
ALTER TABLE [dbo].[Company_Department] ADD  DEFAULT ((1)) FOR [is_active]
GO
ALTER TABLE [dbo].[Company_Department] ADD  DEFAULT (sysdatetime()) FOR [updated_at]
GO
ALTER TABLE [dbo].[Company_ImportState] ADD  DEFAULT (sysdatetime()) FOR [imported_at]
GO
ALTER TABLE [dbo].[Company_OperationSubmission] ADD  DEFAULT (N'待審核') FOR [status]
GO
ALTER TABLE [dbo].[Company_OperationSubmission] ADD  DEFAULT (sysdatetime()) FOR [submitted_at]
GO
ALTER TABLE [dbo].[Company_Staff] ADD  DEFAULT ((1)) FOR [is_active]
GO
ALTER TABLE [dbo].[Company_Staff] ADD  DEFAULT (sysdatetime()) FOR [updated_at]
GO
ALTER TABLE [dbo].[Company_TrainingDocument] ADD  DEFAULT ((1)) FOR [is_active]
GO
ALTER TABLE [dbo].[Company_TrainingDocument] ADD  DEFAULT (sysdatetime()) FOR [imported_at]
GO
ALTER TABLE [dbo].[Company_TrainingQuestion] ADD  DEFAULT ((1)) FOR [is_active]
GO
ALTER TABLE [dbo].[Company_WebSettings] ADD  DEFAULT (sysdatetime()) FOR [updated_at]
GO
ALTER TABLE [dbo].[Company_Attendance]  WITH CHECK ADD  CONSTRAINT [FK_Company_Attendance_Staff] FOREIGN KEY([employee_id])
REFERENCES [dbo].[Company_Staff] ([employee_id])
GO
ALTER TABLE [dbo].[Company_Attendance] CHECK CONSTRAINT [FK_Company_Attendance_Staff]
GO
ALTER TABLE [dbo].[Company_OperationSubmission]  WITH CHECK ADD  CONSTRAINT [FK_Company_OperationSubmission_Category] FOREIGN KEY([category_code])
REFERENCES [dbo].[Company_OperationCategory] ([category_code])
GO
ALTER TABLE [dbo].[Company_OperationSubmission] CHECK CONSTRAINT [FK_Company_OperationSubmission_Category]
GO
ALTER TABLE [dbo].[Company_OperationSubmission]  WITH CHECK ADD  CONSTRAINT [FK_Company_OperationSubmission_Staff] FOREIGN KEY([submitted_by])
REFERENCES [dbo].[Company_Staff] ([employee_id])
GO
ALTER TABLE [dbo].[Company_OperationSubmission] CHECK CONSTRAINT [FK_Company_OperationSubmission_Staff]
GO
ALTER TABLE [dbo].[Company_TrainingQuestion]  WITH CHECK ADD  CONSTRAINT [FK_Company_TrainingQuestion_Document] FOREIGN KEY([document_id])
REFERENCES [dbo].[Company_TrainingDocument] ([document_id])
GO
ALTER TABLE [dbo].[Company_TrainingQuestion] CHECK CONSTRAINT [FK_Company_TrainingQuestion_Document]
GO
ALTER TABLE [dbo].[Company_TrainingSection]  WITH CHECK ADD  CONSTRAINT [FK_Company_TrainingSection_Document] FOREIGN KEY([document_id])
REFERENCES [dbo].[Company_TrainingDocument] ([document_id])
ON DELETE CASCADE
GO
ALTER TABLE [dbo].[Company_TrainingSection] CHECK CONSTRAINT [FK_Company_TrainingSection_Document]
GO
ALTER TABLE [dbo].[Company_Attendance]  WITH CHECK ADD  CONSTRAINT [CK_Company_Attendance_Action] CHECK  (([action]=N'CLOCK_OUT' OR [action]=N'CLOCK_IN'))
GO
ALTER TABLE [dbo].[Company_Attendance] CHECK CONSTRAINT [CK_Company_Attendance_Action]
GO
ALTER TABLE [dbo].[Company_OperationSubmission]  WITH CHECK ADD  CONSTRAINT [CK_Company_OperationSubmission_Quantity] CHECK  (([quantity]>=(0) AND [quantity]<=(9999)))
GO
ALTER TABLE [dbo].[Company_OperationSubmission] CHECK CONSTRAINT [CK_Company_OperationSubmission_Quantity]
GO
ALTER TABLE [dbo].[Company_Staff]  WITH CHECK ADD  CONSTRAINT [CK_Company_Staff_Age] CHECK  (([age] IS NULL OR [age]>=(16) AND [age]<=(100)))
GO
ALTER TABLE [dbo].[Company_Staff] CHECK CONSTRAINT [CK_Company_Staff_Age]
GO
ALTER TABLE [dbo].[Company_TrainingQuestion]  WITH CHECK ADD  CONSTRAINT [CK_Company_TrainingQuestion_Answer] CHECK  (([correct_index]>=(0) AND [correct_index]<=(9)))
GO
ALTER TABLE [dbo].[Company_TrainingQuestion] CHECK CONSTRAINT [CK_Company_TrainingQuestion_Answer]
GO
