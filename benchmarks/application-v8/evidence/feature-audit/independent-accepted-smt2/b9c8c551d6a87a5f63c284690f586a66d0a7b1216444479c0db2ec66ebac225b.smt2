; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x27 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32)))) (bvshl independent_opaque_1 (bvand (_ bv4 32) (_ bv31 32))))))
(let ((?x28 (bvadd independent_opaque_0 ?x27)))
(let ((?x16 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x14 (bvadd (bvshl independent_opaque_1 (bvand (_ bv1 32) (_ bv31 32))) independent_opaque_1)))
(let ((?x20 (bvadd independent_opaque_0 (bvshl ?x14 ?x16))))
(and (distinct ?x20 ?x28) true)))))))
(check-sat)
