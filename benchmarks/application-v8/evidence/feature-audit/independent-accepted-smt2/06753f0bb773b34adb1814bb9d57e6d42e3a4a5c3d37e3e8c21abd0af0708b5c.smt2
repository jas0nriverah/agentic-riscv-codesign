; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x18 (bvshl independent_opaque_0 (bvand (_ bv4 32) (_ bv31 32)))))
(let ((?x165 (bvadd (bvsub (_ bv0 32) independent_opaque_0) ?x18)))
(let ((?x45 (bvsub ?x18 independent_opaque_0)))
(and (distinct ?x45 ?x165) true)))))
(check-sat)
