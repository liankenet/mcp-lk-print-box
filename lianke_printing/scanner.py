from lianke_printing.base import LiankePrintingBase


class LiankeScanning(LiankePrintingBase):
    def scanner_list(self):
        """
        获取扫描仪列表
        :return:
        """
        return self.get(
            "/scanning/scanner_list",
            params={"deviceId": self.device_id, "deviceKey": self.device_key},
        )

    def scanner_status(self, scanning_id: str):
        """
        获取扫描仪状态
        :param scanning_id: 扫描仪ID
        :return:
        """
        return self.get(
            "/scanning/scanner_status",
            params={"deviceId": self.device_id, "deviceKey": self.device_key, "scanningId": scanning_id},
        )

    def scanner_params(self, scanning_id: str):
        """
        获取扫描仪参数
        :param scanning_id: 扫描仪ID
        :return:
        """
        return self.get(
            "/scanning/scanner_params",
            params={"deviceId": self.device_id, "deviceKey": self.device_key, "scanningId": scanning_id},
        )

    def create_scan_job(self, scanning_id: str, **kwargs):
        """
        创建扫描任务
        :param scanning_id: 扫描仪ID
        :param kwargs: 其他扫描参数
        :return:
        """
        post_data = {
            "deviceId": self.device_id,
            "deviceKey": self.device_key,
            "scanningId": scanning_id,
        }
        post_data.update(kwargs)
        return self.post("/scanning/job", json=post_data)

    def query_scan_job(self, task_id: str):
        """
        查询扫描任务
        :param task_id: 任务ID
        :return:
        """
        return self.get(
            "/scanning/job",
            params={"deviceId": self.device_id, "deviceKey": self.device_key, "task_id": task_id},
        )

    def delete_scan_job(self, task_id: str):
        """
        删除扫描任务
        :param task_id: 任务ID
        :return:
        """
        return self.delete(
            "/scanning/job",
            json={"deviceId": self.device_id, "deviceKey": self.device_key, "task_id": task_id},
        )

