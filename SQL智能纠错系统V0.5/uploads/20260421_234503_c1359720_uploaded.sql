!set plsqlUseSlash TRUE
set hive.exec.dynamic.partition=true;
set hive.exec.dynamic.partition.mode=nonstrict;
CREATE OR REPLACE PROCEDURE SP_DWD_DM_T02_MGR_ORG_INFO(
                P_I_BATCHID IN STRING,  -- 脚本执行批次ID
                P_I_JOBID IN STRING,    -- 脚本JOBID
                P_I_DATE IN STRING)     -- 跑批基准日期
                IS 
/************************************************************************************
copy Right   :  *****公司
job_Name     :  SP_DWD_DM_T02_MGR_ORG_INFO
Description  :  统一监管报送平台 - 主管分行信息数据加工
Target Table :  T02_MGR_ORG_INFO
Source Table :  ODM_STO_CIF_BRANCH_EXEC_TFD  主管分行信息表
SystemName   :  统一监管报送平台
ArgoDB       :  5.2
Parameters   :  P_I_BATCHID  脚本执行批次ID
                P_I_JOBID    脚本JOBID
                P_I_DATE     跑批基准日期
Revisions    :  
Ver      DATE      Author    Mode   Dec
------   -------   ------   ------ ------
1.0  20260408  [作者]  Created
**************************************************************************************/
-- 变量声明部分（固定）
V_SQLCOUNT       INT ;   -- 脚本执行影响记录数
V_SHORT_DATE     STRING; --日历组件输出的日期参数(YYYYMMDD格式)
V_LONG_DATE      STRING; -- DM表日期格式(YYYY-MM-DD格式)
V_SP_NAME        STRING; --存储过程英文名称
V_SP_DESC        STRING; --存储过程中文名称
V_STEP_NUM       STRING; --脚本执行步骤
V_RETURN_CD      STRING; --脚本执行数据库错误码
V_RETURN_MSG     STRING; --脚本执行数据库错误信息

BEGIN
-- 初始化变量（固定）
V_SQLCOUNT        :=0;
V_SP_NAME         :='SP_DWD_DM_T02_MGR_ORG_INFO';
V_SP_DESC         :='主管分行信息'; 

/***************************************日期处理逻辑*************************************************/
-- 日期处理（固定）
SP_BIZCOM_CORE_GET_BATCH_DATE(
                    P_I_DATE,               --传入参数
                    'batch_na_base_date',   --需要使用的日历枚举Key
                    V_SHORT_DATE             --返回的结果值
                    );                      --日期获取组件
                    
-- 转换为DM表日期格式(YYYY-MM-DD)（固定）
V_LONG_DATE :=SUBSTR(V_SHORT_DATE,1,4)||'-'||SUBSTR(V_SHORT_DATE,5,2)||'-'||SUBSTR(V_SHORT_DATE,7,2);

/***************************************程序主体*************************************************/
-- 开始执行日志（固定）
V_STEP_NUM    := '1';
SP_BIZCOM_CORE_BIZBATCH_LOG(
                P_I_BATCHID,                                    --输入参数,批次ID
                P_I_JOBID,                                      --存储过程英文名称
                V_SHORT_DATE,                                   --获取的日历跑批基准日期
                V_SP_DESC,                                      --存储过程名称
                'SUCCESS',                                      --日志类型/SUCCESS/FAILED
                CONCAT(V_SP_NAME||'-'||V_SP_DESC,':START'),     --日志信息
                V_STEP_NUM       												--执行步骤
                );
                
-- 删除旧数据（可替换：表名）
DELETE FROM T02_MGR_ORG_INFO WHERE DATA_DATE = V_SHORT_DATE ;
    
-- 获取删除记录数并提交（固定）
V_SQLCOUNT := SQL%ROWCOUNT;
COMMIT;

-- 记录删除操作日志（固定）
SP_BIZCOM_CORE_BIZBATCH_LOG(
                P_I_BATCHID,                                    --输入参数,批次ID
                P_I_JOBID,                                      --存储过程英文名称
                V_SHORT_DATE,                                   --获取的日历跑批基准日期
                V_SP_DESC,                                      --存储过程名称
                'SUCCESS',                                      --日志类型/SUCCESS/FAILED
                CONCAT(V_SP_NAME||'-'||V_SP_DESC,'DELETE COUNT =',V_SQLCOUNT),     --日志信息
                V_STEP_NUM       												--执行步骤
                );

-- 开始插入数据（固定）
-- 分组1 - MP1（主管分行信息）
V_STEP_NUM    := '2';
SP_BIZCOM_CORE_BIZBATCH_LOG(
                P_I_BATCHID,                                    --输入参数,批次ID
                P_I_JOBID,                                      --存储过程英文名称
                V_SHORT_DATE,                                   --获取的日历跑批基准日期
                V_SP_DESC,                                      --存储过程名称
                'SUCCESS',                                      --日志类型/SUCCESS/FAILED
                CONCAT(V_SP_NAME||'-'||V_SP_DESC,':INSERT START (MP1)'),     --日志信息
                V_STEP_NUM       												--执行步骤
                );

-- 插入数据（MP1分组 - 主管分行信息）
INSERT INTO T02_MGR_ORG_INFO PARTITION (DATA_DATE)
(
    UUID,
    LOAD_TIME,
    DATA_DATE,
    ORG_NO,
    ORG_TYPE,
    CUST_NO,
    OFFICER_ID,
    ASSISTANT_ID,
    TEAM_LEADER_ID,
    SECTION_CHIEF_ID,
    SETUP_DATE,
    UPDATE_DATE,
    REMARK_INFO,
    DATA_DEPT,
    DATA_SRC
)
SELECT 
    uuid() AS UUID,
    CURREN_TIMESTAMP() AS LOAD_TIME,
    V_SHORT_DATE AS DATA_DATE,
    T.BRANCH AS ORG_NO,
    CASE 
        WHEN T.BRANCH_EXEC_TYPE = 'M' THEN '011'
        WHEN T.BRANCH_EXEC_TYPE = 'B' THEN '02'
        ELSE NULL
    END AS ORG_TYPE,
    T.CLIENT_NO AS CUST_yes,

    T.ASSISTANT_ID AS ASSISTANT_ID,
    T.TEAM_LEADER_ID AS TEAM_LEADER_ID,
    T.SECTION_CHIEF_ID AS SECTION_CHIEF_ID,
    T.CREATE_DATE AS SETUP_DATE,
    T.UPDATE_DATE AS UPDATE_DATE,
    '123411' AS REMARK_INFO,
    NULL AS DATA_DEPT,
    'MP1' AS DATA_SRC
FROM ODM_STO_CIF_BRANCH_EXEC_TFD T
WHERE T.DATA_DATE = V_SHORT_DATE;

-- 获取插入记录数并提交（固定）
V_SQLCOUNT := SQL%ROWCOUNT;
COMMIT;

-- 记录插入操作日志（MP1）
SP_BIZCOM_CORE_BIZBATCH_LOG(
                P_I_BATCHID,                                    --输入参数,批次ID
                P_I_JOBID,                                      --存储过程英文名称
                V_SHORT_DATE,                                   --获取的日历跑批基准日期
                V_SP_DESC,                                      --存储过程名称
                'SUCCESS',                                      --日志类型/SUCCESS/FAILED
                CONCAT(V_SP_NAME||'-'||V_SP_DESC,':INSERT COUNT (MP1) =',V_SQLCOUNT),     --日志信息
                V_STEP_NUM       												--执行步骤
                );

-- 结束执行日志
V_STEP_NUM    := '3';
SP_BIZCOM_CORE_BIZBATCH_LOG(
                P_I_BATCHID,                                    --输入参数,批次ID
                P_I_JOBID,                                      --存储过程英文名称
                V_SHORT_DATE,                                   --获取的日历跑批基准日期
                V_SP_DESC,                                      --存储过程名称
                'SUCCESS',                                      --日志类型/SUCCESS/FAILED
                CONCAT(V_SP_NAME||'-'||V_SP_DESC,':END'),     --日志信息
                V_STEP_NUM       												--执行步骤
                );

/***************************************异常处理*************************************************/
-- 异常处理（固定）
EXCEPTION
WHEN OTHERS THEN 
V_RETURN_CD     := CAST(sqlcode() AS STRING);
V_RETURN_MSG    := sqlerrm();
SP_BIZCOM_CORE_BIZBATCH_LOG(
                P_I_BATCHID,                                    										--输入参数,批次ID
                P_I_JOBID,                                      										--存储过程英文名称
                V_SHORT_DATE,                                    										--获取的日历跑批基准日期
                V_SP_DESC,                                      										--存储过程名称
                'FAILED',                                      										--日志类型/SUCCESS/FAILED
                CONCAT(V_SP_NAME||'-'||V_SP_DESC,':ERROR_CODE=' ,V_RETURN_CD, ',ERROR_MSG:',V_RETURN_MSG), 	 --日志信息
                V_STEP_NUM       																				--执行步骤
                );
		 RAISE;
END;
