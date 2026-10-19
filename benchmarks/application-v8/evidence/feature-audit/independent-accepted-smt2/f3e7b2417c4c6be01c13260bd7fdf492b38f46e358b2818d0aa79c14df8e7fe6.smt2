; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x566 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32)))) (bvshl independent_opaque_0 (bvand (_ bv4 32) (_ bv31 32))))))
(let ((?x41 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x52 (bvadd (bvshl independent_opaque_0 (bvand (_ bv1 32) (_ bv31 32))) independent_opaque_0)))
(let ((?x35 (bvshl ?x52 ?x41)))
(and (distinct ?x35 ?x566) true))))))
(check-sat)
