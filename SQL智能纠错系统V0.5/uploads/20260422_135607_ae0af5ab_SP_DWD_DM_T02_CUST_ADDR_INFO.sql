!set plsqlUseSlash TRUE
set hive.exec.dynamic.partition=true;
set hive.exec.dynamic.partition.mode=nonstrict;
CREATE OR REPLACE PROCEDURE SP_DWD_DM_T02_CUST_ADDR_INFO(
                P_I_BATCHID IN STRING,  -- 脚本执行批次ID
                P_I_JOBID IN STRING,    -- 脚本JOBID
                P_I_DATE IN STRING)     -- 跑批基准日期
                IS 
/************************************************************************************
copy Right   :  *****公司
job_Name     :  SP_DWD_DM_T02_CUST_ADDR_INFO
Description  :  统一监管报送平台 - 客户物理地址信息数据加工
Target Table :  T02_CUST_ADDR_INFO
Source Table :  ODM_STO_CIF_CLIENT_CONTACT_TBL_TFD  客户联系信息表
             :  ODM_STO_CIF_CLIENT_TFD  客户信息表
             :  ODM_STO_CIF_BRANCH_EXEC_TFD  主管分行信息
             :  MST_COMPANY_BS_INFO  法人基础信息表
             :  MST_FINCLINSTITUTN_BS_INFO  金融机构基础信息表
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
V_SP_NAME         :='SP_DWD_DM_T02_CUST_ADDR_INFO';
V_SP_DESC         :='客户物理地址信息'; 

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
DELETE FROM T02_CUST_ADDR_INFO WHERE DATA_DATE = V_SHORT_DATE ;
    
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
-- 分组1 - MP1（联系地址）
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

-- 插入数据（MP1分组 - 联系地址）
INSERT INTO T02_CUST_ADDR_INFO PARTITION (DATA_DATE)
(
    UUID,
    LOAD_TIME,
    DATA_DATE,
    ORG_NO,
    CUST_NO,
    TEL,
    MOBILE_PHONE,
    MOBILE_PHONE2,
    COUNTRY_AND_DIST_CODE,
    ADDR_TYPE,
    ADMIN_DIVI,
    ZIP,
    DETAIL_ADDR,
    SETUP_DATE,
    LAST_UPDATE_DATE,
    REMARK_INFO,
    DATA_DEPT,
    DATA_SRC
)
SELECT 
    uuid() AS UUID,
    CURRENT_TIMESTAMP() AS LOAD_TIME,
    V_SHORT_DATE AS DATA_DATE,
    T.CONTACT_TYPE AS ORG_NO,
    T.CLIENT_NO AS CUST_NO,
    T.CONTACT_TEL AS TEL,
    T.MOBILE_PHONE AS MOBILE_PHONE,
    T.MOBILE_PHONE2 AS MOBILE_PHONE2,
    T.COUNTRY AS COUNTRY_AND_DIST_CODE,
    '01' AS ADDR_TYPE,
    T.CITY_DIST AS ADMIN_DIVI,
    T.POSTAL_CODE AS ZIP,
    T.ADDRESS AS DETAIL_ADDR,
    T1.CREATE_DATE AS SETUP_DATE,
    T.LAST_CHANGE_DATE AS LAST_UPDATE_DATE,
    NULL AS REMARK_INFO,
    NULL AS DATA_DEPT,
    'MP1' AS DATA_SRC
FROM ODM_STO_CIF_CLIENT_CONTACT_TBL_TFD T
LEFT JOIN ODM_STO_CIF_CLIENT_TFD T1 
    ON T.CLIENT_NO = T1.CLIENT_NO 
    AND T1.DATA_DATE = V_SHORT_DATE
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

-- 开始插入数据（固定）
-- 分组2 - MP2（营业地址）
V_STEP_NUM    := '3';
SP_BIZCOM_CORE_BIZBATCH_LOG(
                P_I_BATCHID,                                    --输入参数,批次ID
                P_I_JOBID,                                      --存储过程英文名称
                V_SHORT_DATE,                                   --获取的日历跑批基准日期
                V_SP_DESC,                                      --存储过程名称
                'SUCCESS',                                      --日志类型/SUCCESS/FAILED
                CONCAT(V_SP_NAME||'-'||V_SP_DESC,':INSERT START (MP2)'),     --日志信息
                V_STEP_NUM       												--执行步骤
                );

-- 插入数据（MP2分组 - 营业地址）
INSERT INTO T02_CUST_ADDR_INFO PARTITION (DATA_DATE)
(
    UUID,
    LOAD_TIME,
    DATA_DATE,
    ORG_NO,
    CUST_NO,
    TEL,
    MOBILE_PHONE,
    MOBILE_PHONE2,
    COUNTRY_AND_DIST_CODE,
    ADDR_TYPE,
    ADMIN_DIVI,
    ZIP,
    DETAIL_ADDR,
    SETUP_DATE,
    LAST_UPDATE_DATE,
    REMARK_INFO,
    DATA_DEPT,
    DATA_SRC
)
SELECT 
    uuid() AS UUID,
    CURRENT_TIMESTAMP() AS LOAD_TIME,
    V_SHORT_DATE AS DATA_DATE,
    T1.BRANCH AS ORG_NO,
    T.CLIENT_NO AS CUST_NO,
    NULL AS TEL,
    NULL AS MOBILE_PHONE,
    NULL AS MOBILE_PHONE2,
    COALESCE(T2.MainBizAddrCtry, T3.MainBizAddrCtry) AS COUNTRY_AND_DIST_CODE,
    '02' AS ADDR_TYPE,
    COALESCE(T2.MainBizAddrAreaOrCounty, T2.MainBizAddrCity, T2.MainBizAddrPrvn, T3.MainBizAddrAreaOrCounty, T3.MainBizAddrCity, T3.MainBizAddrPrvn) AS ADMIN_DIVI,
    COALESCE(T2.MainBizAddrPostcode, T3.MainBizAddrPostcode) AS ZIP,
    COALESCE(T2.MainBizAddr, T3.MainBizAddr) AS DETAIL_ADDR,
    COALESCE(T2.DtOfIncorporation, T3.DtOfIncorporation) AS SETUP_DATE,
    NULL AS LAST_UPDATE_DATE,
    NULL AS REMARK_INFO,
    NULL AS DATA_DEPT,
    'MP2' AS DATA_SRC
FROM ODM_STO_CIF_CLIENT_TFD T
LEFT JOIN ODM_STO_CIF_BRANCH_EXEC_TFD T1 
    ON T.CLIENT_NO = T1.CLIENT_NO 
    AND T1.DATA_DATE = V_SHORT_DATE 
    AND T1.BRANCH_EXEC_TYPE = 'M'
LEFT JOIN MST_COMPANY_BS_INFO T2 
    ON T.CLIENT_NO = T2.CIFCode
    AND T2.DATA_DATE = V_SHORT_DATE
LEFT JOIN MST_FINCLINSTITUTN_BS_INFO T3 
    ON T.CLIENT_NO = T3.CIFCode
    AND T3.DATA_DATE = V_SHORT_DATE
WHERE T.DATA_DATE = V_SHORT_DATE;

-- 获取插入记录数并提交（固定）
V_SQLCOUNT := SQL%ROWCOUNT;
COMMIT;

-- 记录插入操作日志（MP2）
SP_BIZCOM_CORE_BIZBATCH_LOG(
                P_I_BATCHID,                                    --输入参数,批次ID
                P_I_JOBID,                                      --存储过程英文名称
                V_SHORT_DATE,                                   --获取的日历跑批基准日期
                V_SP_DESC,                                      --存储过程名称
                'SUCCESS',                                      --日志类型/SUCCESS/FAILED
                CONCAT(V_SP_NAME||'-'||V_SP_DESC,':INSERT COUNT (MP2) =',V_SQLCOUNT),     --日志信息
                V_STEP_NUM       												--执行步骤
                );

-- 开始插入数据（固定）
-- 分组3 - MP3（其他地址）
V_STEP_NUM    := '4';
SP_BIZCOM_CORE_BIZBATCH_LOG(
                P_I_BATCHID,                                    --输入参数,批次ID
                P_I_JOBID,                                      --存储过程英文名称
                V_SHORT_DATE,                                   --获取的日历跑批基准日期
                V_SP_DESC,                                      --存储过程名称
                'SUCCESS',                                      --日志类型/SUCCESS/FAILED
                CONCAT(V_SP_NAME||'-'||V_SP_DESC,':INSERT START (MP3)'),     --日志信息
                V_STEP_NUM       												--执行步骤
                );

-- 插入数据（MP3分组 - 其他地址）
INSERT INTO T02_CUST_ADDR_INFO PARTITION (DATA_DATE)
(
    UUID,
    LOAD_TIME,
    DATA_DATE,
    ORG_NO,
    CUST_NO,
    TEL,
    MOBILE_PHONE,
    MOBILE_PHONE2,
    COUNTRY_AND_DIST_CODE,
    ADDR_TYPE,
    ADMIN_DIVI,
    ZIP,
    DETAIL_ADDR,
    SETUP_DATE,
    LAST_UPDATE_DATE,
    REMARK_INFO,
    DATA_DEPT,
    DATA_SRC
)
SELECT 
    uuid() AS UUID,
    CURRENT_TIMESTAMP() AS LOAD_TIME,
    V_SHORT_DATE AS DATA_DATE,
    T1.BRANCH AS ORG_NO,
    T.CLIENT_NO AS CUST_NO,
    NULL AS TEL,
    NULL AS MOBILE_PHONE,
    NULL AS MOBILE_PHONE2,
    COALESCE(T2.OthrAddrCtry, T3.OthrAddrCtry) AS COUNTRY_AND_DIST_CODE,
    '99' AS ADDR_TYPE,
    COALESCE(T2.OthrAddrAreaOrCounty, T2.OthrAddrCity, T2.OthrAddrPrvn, T3.OthrAddrAreaOrCounty, T3.OthrAddrCity, T3.OthrAddrPrvn) AS ADMIN_DIVI,
    COALESCE(T2.OthrAddrPostcode, T3.OthrAddrPostcode) AS ZIP,
    COALESCE(T2.OthrAddr, T3.OthrAddr) AS DETAIL_ADDR,
    COALESCE(T2.DtOfIncorporation, T3.DtOfIncorporation) AS SETUP_DATE,
    NULL AS LAST_UPDATE_DATE,
    COALESCE(T2.OthrAddrTypeDescr, T3.OthrAddrTypeDescr) AS REMARK_INFO,
    NULL AS DATA_DEPT,
    'MP3' AS DATA_SRC
FROM ODM_STO_CIF_CLIENT_TFD T
LEFT JOIN ODM_STO_CIF_BRANCH_EXEC_TFD T1 
    ON T.CLIENT_NO = T1.CLIENT_NO 
    AND T1.DATA_DATE = V_SHORT_DATE 
    AND T1.BRANCH_EXEC_TYPE = 'M'
LEFT JOIN MST_COMPANY_BS_INFO T2 
    ON T.CLIENT_NO = T2.CIFCode
    AND T2.DATA_DATE = V_SHORT_DATE
    AND T2.OthrAddrIsOrNot = '有'
LEFT JOIN MST_FINCLINSTITUTN_BS_INFO T3 
    ON T.CLIENT_NO = T3.CIFCode
    AND T3.DATA_DATE = V_SHORT_DATE
    AND T3.OthrAddrIsOrNot = '有'
WHERE T.DATA_DATE = V_SHORT_DATE;

-- 获取插入记录数并提交（固定）
V_SQLCOUNT := SQL%ROWCOUNT;
COMMIT;

-- 记录插入操作日志（MP3）
SP_BIZCOM_CORE_BIZBATCH_LOG(
                P_I_BATCHID,                                    --输入参数,批次ID
                P_I_JOBID,                                      --存储过程英文名称
                V_SHORT_DATE,                                   --获取的日历跑批基准日期
                V_SP_DESC,                                      --存储过程名称
                'SUCCESS',                                      --日志类型/SUCCESS/FAILED
                CONCAT(V_SP_NAME||'-'||V_SP_DESC,':INSERT COUNT (MP3) =',V_SQLCOUNT),     --日志信息
                V_STEP_NUM       												--执行步骤
                );

-- 结束执行日志
V_STEP_NUM    := '5';
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
