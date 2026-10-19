; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x22 (bvadd (bvshl independent_opaque_0 (bvand (_ bv1 32) (_ bv31 32))) (bvshl independent_opaque_1 (bvand (_ bv1 32) (_ bv31 32))))))
(let ((?x60 (bvand (_ bv1 32) (_ bv31 32))))
(let ((?x45 (bvshl (bvadd independent_opaque_0 independent_opaque_1) ?x60)))
(and (distinct ?x45 ?x22) true)))))
(check-sat)
