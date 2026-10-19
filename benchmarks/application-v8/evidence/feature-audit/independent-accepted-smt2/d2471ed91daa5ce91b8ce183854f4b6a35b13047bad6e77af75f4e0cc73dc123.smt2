; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x431 (bvadd (bvsub (_ bv0 32) independent_opaque_1) (bvshl independent_opaque_1 (bvand (_ bv4 32) (_ bv31 32))))))
(let ((?x165 (bvadd (bvsub (_ bv0 32) independent_opaque_0) (bvshl independent_opaque_0 (bvand (_ bv4 32) (_ bv31 32))))))
(let ((?x194 (bvadd ?x165 ?x431)))
(let ((?x13 (bvadd independent_opaque_0 independent_opaque_1)))
(let ((?x47 (bvsub (bvshl ?x13 (bvand (_ bv4 32) (_ bv31 32))) ?x13)))
(and (distinct ?x47 ?x194) true)))))))
(check-sat)
