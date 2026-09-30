import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import TruncatedSVD

def recommend_questions_with_weights(user_email: str,
                                     course_id: int, 
                                     num_questions: int, 
                                     merged_data: pd.DataFrame,
                                     question_type: str = None,
                                     low_score_weight: float = 0.4, 
                                     long_time_weight: float = 0.3, 
                                     global_error_weight: float = 0.3):
    # 按题型过滤数据
    if question_type:
        merged_data = merged_data[merged_data['question_type'] == question_type]
    user_data = merged_data[(merged_data['user_email'] == user_email) & (merged_data['course_id'] == course_id)]
    
    # 错题复习逻辑
    low_score_questions = user_data[user_data['score'] < 60].sort_values(by='score').copy()
    low_score_recommendations = low_score_questions[['test_case_id', 'score']].copy()
    low_score_recommendations['weighted_score'] = low_score_recommendations['score'] * low_score_weight

    # 时间过长题目复习逻辑
    long_time_questions = user_data[user_data['consume_time'] > user_data['consume_time'].mean()].copy()
    long_time_recommendations = long_time_questions[['test_case_id', 'consume_time']].copy()
    long_time_recommendations['weighted_time'] = long_time_recommendations['consume_time'] * long_time_weight

    # 全局错题推荐逻辑
    global_high_error_questions = merged_data[(merged_data['course_id'] == course_id) & 
                                              (merged_data['score'] < 60)]
    
    # 计算全局错误率并赋权重
    error_rates = global_high_error_questions.groupby('test_case_id').size().reset_index(name='error_count')
    error_rates['weighted_error'] = error_rates['error_count'] * global_error_weight
    global_error_recommendations = error_rates[['test_case_id', 'weighted_error']].sort_values(by='weighted_error', ascending=False)
    
    # 综合推荐
    recommendations = pd.concat([
        low_score_recommendations[['test_case_id', 'weighted_score']],
        long_time_recommendations[['test_case_id', 'weighted_time']],
        global_error_recommendations[['test_case_id', 'weighted_error']]
    ])
    
    # 合并权重，去重，并根据总权重排序
    recommendations = recommendations.groupby('test_case_id').sum().reset_index()
    recommendations['total_weight'] = recommendations[['weighted_score', 'weighted_time', 'weighted_error']].sum(axis=1)
    recommendations = recommendations.sort_values(by='total_weight', ascending=False)
    
    # 确保推荐题目数量不超过指定数量
    recommendations = recommendations.head(num_questions)
    
    # 返回推荐题目的详细信息
    final_recommendations = merged_data[merged_data['test_case_id'].isin(recommendations['test_case_id'])]
    
    return final_recommendations

def dynamic_adjustment(user_email: str, course_id: int, merged_data: pd.DataFrame, question_type: str = None):
    if question_type:
        merged_data = merged_data[merged_data['question_type'] == question_type]
    # 获取用户的考试记录和题目出现频率
    user_data = merged_data[(merged_data['user_email'] == user_email) & (merged_data['course_id'] == course_id)]
    question_frequency = user_data['test_case_id'].value_counts().reset_index(name='freq')
    question_frequency.rename(columns={'index': 'test_case_id'}, inplace=True)
    
    # 找出用户经常答对的题目，减少推荐
    frequently_correct = user_data[(user_data['score'] >= 80) & 
                                   (user_data['test_case_id'].isin(question_frequency[question_frequency['freq'] > 1]['test_case_id']))]
    
    # 返回这些经常答对的题目的 test_case_id 列表
    reduce_recommendation_ids = frequently_correct['test_case_id'].unique()
    
    return reduce_recommendation_ids

def collaborative_filtering_recommend(user_email: str, course_id: int, num_questions: int, merged_data: pd.DataFrame, question_type: str = None):
    if question_type:
        merged_data = merged_data[merged_data['question_type'] == question_type]

    # 创建用户-题目评分矩阵
    user_question_matrix = merged_data.pivot_table(index='user_email', columns='test_case_id', values='score')
    
    if user_email not in user_question_matrix.index:
        return pd.DataFrame()
    
    initial_n_components = min(max(int(0.2 * user_question_matrix.shape[1]), 50), user_question_matrix.shape[1])

    # 使用初步的SVD进行矩阵分解
    svd = TruncatedSVD(n_components=initial_n_components, random_state=42)
    latent_matrix = svd.fit_transform(user_question_matrix.fillna(0)) 
    
    # 计算累积解释方差，确定最优 n_components
    cumulative_variance = svd.explained_variance_ratio_.cumsum()
    optimal_n_components = (cumulative_variance >= 0.90).argmax() + 1 # 保留90%的信息
    
    # 重新调整 n_components
    svd = TruncatedSVD(n_components=optimal_n_components, random_state=42)
    latent_matrix = svd.fit_transform(user_question_matrix.fillna(0))
    
    # 使用SVD进行矩阵分解
    # svd = TruncatedSVD(n_components=100, random_state=42)
    # latent_matrix = svd.fit_transform(user_question_matrix.fillna(0))
    
    # 计算用户之间的相似度
    user_similarity = cosine_similarity(latent_matrix)
    
    # 找到与目标用户最相似的用户
    user_idx = user_question_matrix.index.get_loc(user_email)
    similar_users = pd.Series(user_similarity[user_idx]).sort_values(ascending=False)
    
    # 基于相似用户的表现进行推荐
    similar_user_emails = similar_users.index[1:min(10, len(similar_users))]
    similar_user_data = merged_data[merged_data['user_email'].isin(similar_user_emails) & 
                                    (merged_data['course_id'] == course_id)]
    
    # 按照题目得分进行推荐
    recommended_questions = similar_user_data.groupby('test_case_id').mean().sort_values(by='score', ascending=True)
    recommended_questions = recommended_questions.replace([np.inf, -np.inf], np.nan).fillna(0)
    return merged_data[merged_data['test_case_id'].isin(recommended_questions.head(num_questions).index)]


def historical_performance_learning(user_email: str, course_id: int, num_questions: int, merged_data: pd.DataFrame, question_type: str = None):
    if question_type:
        merged_data = merged_data[merged_data['question_type'] == question_type]

    # 获取用户的考试记录，按照时间排序
    user_data = merged_data[(merged_data['user_email'] == user_email) & (merged_data['course_id'] == course_id)].sort_values(by='create_time')
    
    # 分析用户的进步情况
    user_data['performance_trend'] = user_data.groupby('test_case_id')['score'].diff().fillna(0)
    
    # 找到进步显著的题目，减少推荐频率
    improved_questions = user_data[(user_data['performance_trend'] > 10) & (user_data['score'] > 70)]
    reduce_recommendation_ids = improved_questions['test_case_id'].unique()
    
    # 调整后的推荐
    recommendations = recommend_questions_with_weights(user_email, course_id, num_questions * 2, merged_data)
    recommendations = recommendations[~recommendations['test_case_id'].isin(reduce_recommendation_ids)]
    
    return recommendations.head(num_questions)


def comprehensive_recommendation_system(user_email: str,
                                        course_id: int, 
                                        num_questions: int, 
                                        merged_data: pd.DataFrame,
                                        question_type: str = None,
                                        low_score_weight: float = 0.4, 
                                        long_time_weight: float = 0.3, 
                                        global_error_weight: float = 0.3):
    # 1. 基于个性化权重分配的初步推荐
    weighted_recommendations = recommend_questions_with_weights(
        user_email=user_email,
        course_id=course_id,
        num_questions=num_questions,
        merged_data=merged_data,
        question_type =question_type,
        low_score_weight=low_score_weight,
        long_time_weight=long_time_weight,
        global_error_weight=global_error_weight
    )
    
    # 2. 结合协同过滤推荐
    collaborative_recommendations = collaborative_filtering_recommend(user_email, course_id, num_questions, merged_data, question_type)
    
    # 3. 基于历史表现调整推荐
    historical_recommendations = historical_performance_learning(user_email, course_id, num_questions, merged_data, question_type)
    
    # 4. 合并所有推荐结果
    all_recommendations = pd.concat([
        weighted_recommendations,
        collaborative_recommendations if not collaborative_recommendations.empty else pd.DataFrame(),
        historical_recommendations
    ])
    
    # 5. 过滤掉用户经常答对的题目
    reduce_recommendation_ids = dynamic_adjustment(user_email, course_id, num_questions, merged_data, question_type)
    final_recommendations = all_recommendations[~all_recommendations['test_case_id'].isin(reduce_recommendation_ids)]
    
    # 6. 计算每个题目在几个推荐算法中出现
    final_recommendations['recommend_count'] = final_recommendations.groupby('test_case_id')['test_case_id'].transform('count')
    
    # 7. 先推荐那些被多个算法推荐的题目
    final_recommendations = final_recommendations.sort_values(by=['recommend_count'], ascending=[False])
    
    # 8. 去重并限制结果数量
    final_recommendations = final_recommendations.drop_duplicates(subset='test_case_id').head(num_questions)

    final_recommendations = final_recommendations.replace([np.inf, -np.inf], np.nan).fillna(0)
    final_recommendations = final_recommendations.applymap(lambda x: np.clip(x, -1e10, 1e10) if isinstance(x, (int, float)) else x)

    final_recommendations_dict = final_recommendations.to_dict(orient='records')

    for item in final_recommendations_dict:
        for key, value in item.items():
            if isinstance(value, float) and value.is_integer():
                item[key] = int(value)
    
    return final_recommendations_dict

