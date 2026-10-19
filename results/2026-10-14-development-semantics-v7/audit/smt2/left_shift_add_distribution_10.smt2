(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x138 (bvshl y (_ bv10 32))))
(let ((?x134 (bvshl x (_ bv10 32))))
(let ((?x139 (bvadd ?x134 ?x138)))
(let ((?x19 (bvadd x y)))
(let ((?x137 (bvshl ?x19 (_ bv10 32))))
(and (distinct ?x137 ?x139) true)))))))
(check-sat)
