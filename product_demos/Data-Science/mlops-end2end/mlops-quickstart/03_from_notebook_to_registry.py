# Databricks notebook source
# MAGIC %md
# MAGIC # Managing the model lifecycle with UC Model Registry
# MAGIC
# MAGIC <img src="https://github.com/QuentinAmbard/databricks-demo/raw/main/product_demos/mlops-end2end-flow-4.png" width="1200">
# MAGIC
# MAGIC One of the primary challenges among data scientists and ML engineers is the absence of a central repository for models, their versions, and the means to manage them throughout their lifecycle.
# MAGIC
# MAGIC [The Unity-Catalog Model Registry](https://docs.databricks.com/en/mlflow/models-in-uc.html) addresses this challenge and enables members of the data team to:
# MAGIC <br><br>
# MAGIC * **Discover** registered models, current aliases in model development, experiment runs, and associated code with a registered model
# MAGIC * **Tag** models to different stages of their lifecycle
# MAGIC * **Deploy** different versions of a registered model in different stages, offering MLOps engineers ability to deploy and conduct testing of different model versions
# MAGIC * **Test** models in an automated fashion
# MAGIC * **Document** models throughout their lifecycle
# MAGIC * **Secure** access and permission for model registrations, transitions or modifications
# MAGIC
# MAGIC <!-- Collect usage data (view). Remove it to disable collection. View README for more details.  -->
# MAGIC <img width="1px" src="https://www.google-analytics.com/collect?v=1&gtm=GTM-NKQ8TT7&tid=UA-163989034-1&cid=555&aip=1&t=event&ec=field_demos&ea=display&dp=%2F42_field_demos%2Ffeatures%2Fmlops%2F04_deploy_to_registry&dt=MLOPS">
# MAGIC <!-- [metadata={"description":"MLOps end2end workflow: Move model to registry and request transition to STAGING.",
# MAGIC  "authors":["quentin.ambard@databricks.com"],
# MAGIC  "db_resources":{},
# MAGIC   "search_tags":{"vertical": "retail", "step": "Data Engineering", "components": ["mlflow"]},
# MAGIC                  "canonicalUrl": {"AWS": "", "Azure": "", "GCP": ""}}] -->

# COMMAND ----------

# MAGIC %md
# MAGIC ## How to Use the Model Registry
# MAGIC Typically, data scientists who use MLflow will conduct many experiments, each with a number of runs that track and log metrics and parameters. During the course of this development cycle, they will select the best run within an experiment and register its model in the registry.  Think of this as **committing** the model to the registry, much as you would commit code to a version control system.
# MAGIC
# MAGIC The registry proposes free-text model alias i.e. `Baseline`, `Challenger`, `Champion` along with tagging.
# MAGIC
# MAGIC Users with appropriate permissions can create models, modify aliases and tags, use models etc.

# COMMAND ----------

# MAGIC %run ../_resources/00-setup

# COMMAND ----------

# MAGIC %md
# MAGIC ## Programmatically find best run and push model to the registry for validation
# MAGIC
# MAGIC We'll programatically select the best model from our last ML experiment and deploy it in the registry. We can easily do that using MLFlow `search_runs` API:

# COMMAND ----------

print(f"Finding best run from {churn_experiment_name}_* and pushing new model version to {model_name}")

# COMMAND ----------

xp_path = "/Shared/dbdemos/experiments/mlops"
filter_string=f"name LIKE '{xp_path}%'"
experiment_id = mlflow.search_experiments(filter_string=filter_string, order_by=["last_update_time DESC"])[0].experiment_id
print(experiment_id)

# COMMAND ----------

# Optional: Load MLflow Experiment and see all runs
df = spark.read.format("mlflow-experiment").load(experiment_id)
display(df)

# COMMAND ----------

# Let's get our best ml run
best_model = mlflow.search_runs(
  experiment_ids=experiment_id,
  order_by=["metrics.test_f1_score DESC"],
  max_results=1,
  filter_string="status = 'FINISHED' and run_name='mlops_best_run'" #filter on mlops_best_run to always use the notebook 02 to have a more predictable demo
)
best_model

# COMMAND ----------

# MAGIC %md Once we have our best model, we can now deploy it in production using it's run ID

# COMMAND ----------

run_id = best_model.iloc[0]['run_id']

client = MlflowClient()
# Set tags to run in order to facilitate validation job
client.set_tag(run_id, key='labels_table', value=f"{catalog}.{db}.mlops_churn_labels") # Note: we could also get this from lineage info
client.set_tag(run_id, key='feature_table', value=f"{catalog}.{db}.mlops_churn_features") # Note: we could also get this from lineage info
client.set_tag(run_id, key='demographic_vars', value="senior_citizen,gender")

# COMMAND ----------

model_name = f"{catalog}.{dbName}.mlops_churn"
# Register best model from experiments run to MLflow model registry
model_details = mlflow.register_model(f"runs:/{run_id}/sklearn_model", model_name)
#model_version_details = client.get_model_version(name=model_name, version=model_details.version)

# COMMAND ----------

# MAGIC %md
# MAGIC At this point the model will have no aliases and meta-data/info.  Let's update the description before triggering a validation job to label/alias as `Challenger`

# COMMAND ----------

# MAGIC %md
# MAGIC ## Set/Update Model Description
# MAGIC We'll do this for the registered model overall.

# COMMAND ----------

# The main model description, typically done once.
client.update_registered_model(
  name=model_details.name,
  description="This model predicts whether a customer will churn using the churn features feature table. It is used to power the Telco Churn Dashboard in DB SQL.",
)

# COMMAND ----------

# MAGIC %md
# MAGIC And add some more details on the new version we just registered

# COMMAND ----------

# Gives more details on this specific model version
best_score = best_model['metrics.test_f1_score'].values[0]
run_name = best_model['tags.mlflow.runName'].values[0]
version_desc = f"This model version has an accuracy/F1 validation metric of {round(best_score,2)*100}%"

client.update_model_version(
  name=model_details.name,
  version=model_details.version,
  description=version_desc
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next: MLOps model testing and validation
# MAGIC
# MAGIC A validation job will start, testing the new model being deployed and validating the request.
# MAGIC
# MAGIC If the model passes all the tests, it'll be accepted and moved into Challenger. Otherwise it'll be rejected, and a slack notification will be sent.
# MAGIC
# MAGIC Next:
# MAGIC  * Find out how the model is being tested befored labbeled as `Challenger` [using the model validation test notebook]($./04_job_challenger_validation)
# MAGIC  * Or discover how to [run Batch and Real-time inference from our Challenger model]($./05_batch_inference)
# MAGIC
# MAGIC ### TODOs: _(TBC)_
# MAGIC  * Promote model from `dev` to `staging` catalog ? (according to recommended catalog-based promotion in [UC](https://docs.gcp.databricks.com/en/machine-learning/manage-model-lifecycle/upgrade-workflows.html#im-used-to-model-version-stage-transitions-how-do-i-promote-a-model-across-environments))

# COMMAND ----------


