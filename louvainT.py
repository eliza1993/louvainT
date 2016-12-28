#!usr/bin/python
# -*- coding: utf-8 -*-

import MySQLdb

"""
实现连接关联和主题关联结合的louvain算法：
1、读数据库获取链接关系
2、开始louvian算法计算
3、计算ΔQ的时候加入主题相似度
2、将分得的社区结果存储入数据库Community

Args:
    SiteRelation:存储链接关系的表，SiteTopic：存储链接关系的数据库

Return:
    Community：站点归属表

Created on 20161227
@author: HU Yi
"""

'''
数据库
'''
db_host = '127.0.0.1'
db_port = 3306
db_username = 'root'
db_password =  'mysql'
db_database_name = 'Freebuf_Secpulse'
db_relation_name = 'SiteRelation'

class PyLouvain:
    '''
    从SiteRelation构建图
    从_path构建图.
    _path: 路径——指向包含边"node_from node_to" （每行一个）的文件
    '''
    @classmethod
    def from_database(cls,dbname):
        record_limit = 1000
        id = 0
        nodes = {}
        edges = []
        conn = MySQLdb.connect(host=db_host, user=db_username, passwd=db_password, db=db_database_name, port=db_port, charset='utf8')
        cur = conn.cursor()
        sql  = "select id,masterSite,outLinkSite,outLinkCount from " + dbname + " where id > " + str(id) +" order by id asc limit " + str(record_limit);
        cur.execute(sql)
        records = cur.fetchall()
        while records:
            for record in records:
                if not record:
                    break
                nodes[record[1]] = 1
                nodes[record[2]] = 1
                w = int(record[3])
                edges.append(((record[1],record[2]),w))
            nodes_,edges_ = in_order(nodes,edges)
            print("%d nodes, %d edges" % (len(nodes_), len(edges_)))
            id += 1000
            sql  = "select id,masterSite,outLinkSite,outLinkCount from " + dbname + " where id > " + str(id) +" order by id asc limit " + str(record_limit);
            cur.execute(sql)
            records = cur.fetchall()

        return cls(nodes_, edges_)



    def __init__(self, nodes, edges):
        self.nodes = nodes
        self.edges = edges
        # 预计算 m (网络中所有链路的权重和)
        #       k_i (入射到节点i的链路的权重和)
        self.m = 0
        self.k_i = [0 for n in nodes]
        self.edges_of_node = {}
        self.w = [0 for n in nodes]
        for e in edges:
            self.m += e[1]
            self.k_i[e[0][0]] += e[1]
            self.k_i[e[0][1]] += e[1] # 最初没有自循环
            # 按节点保存边
            if e[0][0] not in self.edges_of_node:
                self.edges_of_node[e[0][0]] = [e]
            else:
                self.edges_of_node[e[0][0]].append(e)
            if e[0][1] not in self.edges_of_node:
                self.edges_of_node[e[0][1]] = [e]
            elif e[0][0] != e[0][1]:
                self.edges_of_node[e[0][1]].append(e)
        # 在O（1）的时间中访问节点的社区
        self.communities = [n for n in nodes]
        self.actual_partition = []



    '''
        应用Louvain算法.
    '''
    def apply_method(self):
        network = (self.nodes, self.edges)
        best_partition = [[node] for node in network[0]]
        best_q = -1
        i = 1
        while 1:
            print("pass #%d" % i)
            i += 1
            partition = self.first_phase(network) #初始分区
            q = self.compute_modularity(partition)
            print "q = %s" % q
            partition = [c for c in partition if c]
            #print("%s (%.8f)" % (partition, q))
            # 用分区聚簇初始节点  压缩
            if self.actual_partition:
                actual = []
                for p in partition:
                    part = []
                    for n in p:
                        part.extend(self.actual_partition[n])
                    actual.append(part)
                self.actual_partition = actual
            else:
                self.actual_partition = partition

            #没有变化就退出完成
            if q == best_q:
                break
            network = self.second_phase(network, partition)
            best_partition = partition
            best_q = q
            #print("pass #%d" % i)
            #i += 1
            print "best Q = %s" % (best_q)
        return (self.actual_partition, best_q)


    '''
        计算当前网络的模块度。
        partition：节点列表
    '''
    def compute_modularity(self, partition):
        q = 0.0
        m2 = self.m * 2.0
        for i in range(len(partition)):
            q += self.s_in[i] / m2 - (self.s_tot[i] / m2) ** 2
        return q

    '''
        计算社区_c中具有节点的模块化增益。
         _node：int
         _c：int community
         _k_i_in：从_node到_c中的节点的链接的权重的总和
         k_i_in为什么要乘2 ?????????????????（源代码k_in_in前面有‘2 *’,根据公式认为2*多余，故这里删去）
    '''
    def compute_modularity_gain(self, node, c, k_i_in):
        return k_i_in - self.s_tot[c] * self.k_i[node] / self.m

    '''
        执行方法的第一阶段。
         _network：（nodes，edges）
    '''
    def first_phase(self, network):
        # 进行初始分区
        best_partition = self.make_initial_partition(network)
        while 1:
            improvement = 0
            for node in network[0]:
                node_community = self.communities[node]
                # 默认最佳社区是其自身
                best_community = node_community
                best_gain = 0
                # 从其社区中删除_node
                best_partition[node_community].remove(node)
                best_shared_links = 0

                for e in self.edges_of_node[node]:
                    if e[0][0] == e[0][1]:
                        continue
                        #如果点和邻居节点在同一个社区，则best_shared_links +1
                    if e[0][0] == node and self.communities[e[0][1]] == node_community or e[0][1] == node and self.communities[e[0][0]] == node_community:
                        best_shared_links += e[1]
                #一个点移除社区后内部权重外部权重同时减少
                self.s_in[node_community] -= 2 * (best_shared_links + self.w[node])
                self.s_tot[node_community] -= self.k_i[node]

                #把原来节点所在社区置为-1
                self.communities[node] = -1

                communities = {} # 只考虑不同社区的邻居
                for neighbor in self.get_neighbors(node):
                    #邻居节点所在社区
                    community = self.communities[neighbor]
                    if community in communities:
                        continue

                    communities[community] = 1
                    shared_links = 0
                    for e in self.edges_of_node[node]:
                        if e[0][0] == e[0][1]:
                            continue

                        #计算新社区的增加的内部权重
                        if e[0][0] == node and self.communities[e[0][1]] == community or e[0][1] == node and self.communities[e[0][0]] == community:
                            shared_links += e[1]
                    # 计算通过将_node移动到_neighbor的社区获得的模块性增益
                    gain = self.compute_modularity_gain(node, community, shared_links)
                    if gain > best_gain:
                        #print "gain %s > best_gain: %s" % (gain,best_gain)
                        best_community = community
                        best_gain = gain
                        best_shared_links = shared_links
                # 将_node插入模块性增益最大的社区
                best_partition[best_community].append(node)
                self.communities[node] = best_community
                self.s_in[best_community] += 2 * (best_shared_links + self.w[node])
                self.s_tot[best_community] += self.k_i[node]
                if node_community != best_community:
                    improvement = 1


            if not improvement:
                break
        return best_partition

    '''
        产生与_node相邻的节点。
         _node：int
    '''
    def get_neighbors(self, node):
        for e in self.edges_of_node[node]:
            if e[0][0] == e[0][1]: # 节点不与其自身相邻
                continue
            if e[0][0] == node:
                yield e[0][1]
            if e[0][1] == node:
                yield e[0][0]

    '''
        从_network构建初始分区。
          _network：（nodes，edges）
    '''
    def make_initial_partition(self, network):
        partition = [[node] for node in network[0]]
        self.s_in = [0 for node in network[0]]
        self.s_tot = [self.k_i[node] for node in network[0]]
        for e in network[1]:
            if e[0][0] == e[0][1]: # 只有自循环
                self.s_in[e[0][0]] += e[1]
                self.s_in[e[0][1]] += e[1]
        return partition

    '''
       执行方法的第二阶段。
         _network：（nodes，edges）
         _partition：节点的列表
    '''
    def second_phase(self, network, partition):
        nodes_ = [i for i in range(len(partition))]

        # 重新分配社区
        communities_ = []
        d = {}
        i = 0
        for community in self.communities:
            if community in d:
                communities_.append(d[community])
            else:
                d[community] = i
                communities_.append(i)
                i += 1


        self.communities = communities_

        # 重造相连的边
        edges_ = {}
        for e in network[1]:
            #用社区id作为新节点坐标 并计算权重
            ci = self.communities[e[0][0]]
            cj = self.communities[e[0][1]]
            try:
                edges_[(ci, cj)] += e[1]
            except KeyError:
                edges_[(ci, cj)] = e[1]

        edges_ = [(k, v) for k, v in edges_.items()]

        # 重新计算k_i向量并且按节点存储边缘
        self.k_i = [0 for n in nodes_]
        self.edges_of_node = {}
        self.w = [0 for n in nodes_]
        for e in edges_:
            self.k_i[e[0][0]] += e[1]
            self.k_i[e[0][1]] += e[1]
            if e[0][0] == e[0][1]:
                self.w[e[0][0]] += e[1]
            if e[0][0] not in self.edges_of_node:
                self.edges_of_node[e[0][0]] = [e]
            else:
                self.edges_of_node[e[0][0]].append(e)
            if e[0][1] not in self.edges_of_node:
                self.edges_of_node[e[0][1]] = [e]
            elif e[0][0] != e[0][1]:
                self.edges_of_node[e[0][1]].append(e)
        # 重置社区
        self.communities = [n for n in nodes_]
        return (nodes_, edges_)

'''
    重建具有连续节点标识的图。
     _nodes：int型
     _edges：（（int，int），weight）
'''
def in_order(nodes, edges):
        # 重建具有连续标识符的图
        nodes = list(nodes.keys()) #key按顺序输出为list
        nodes.sort() #排序
        i = 0
        nodes_ = []
        d = {}
        for n in nodes:
            nodes_.append(i)
            d[n] = i
            i += 1
        edges_ = []
        for e in edges:
            edges_.append(((d[e[0][0]], d[e[0][1]]), e[1]))
        return (nodes_, edges_)
